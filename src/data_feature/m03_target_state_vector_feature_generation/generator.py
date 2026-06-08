"""Deterministic Layer 3 target state-vector feature generator.

The generator consumes already-cleaned target-local bars, anonymous target
candidate rows, and optional point-in-time Layer 1/2 context rows. It performs no
provider calls and no database writes. SQL/request wrappers should own runtime
reads and writes once the storage contract is accepted.
"""
from __future__ import annotations

import csv
import json
import math
from bisect import bisect_left, bisect_right
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
FEATURE = "m03_target_state_vector_feature_generation"
DEFAULT_VECTOR_VERSION = "target_context_state"
DEFAULT_RUN_ID = "adhoc"
STATE_WINDOW_MINUTES: dict[str, int] = {
    "10min": 10,
    "1h": 60,
    "1D": 24 * 60,
    "1W": 7 * 24 * 60,
}
STATE_WINDOW_LABELS = tuple(STATE_WINDOW_MINUTES)
STATE_WINDOW_SYNC_POLICY = "market_sector_target_blocks_must_share_identical_observation_windows"
METADATA_COLUMNS = {
    "run_id",
    "source_run_ref",
    "available_time",
    "tradeable_time",
    "target_candidate_id",
    "market_context_state_ref",
    "sector_context_state_ref",
    "target_context_state_version",
}


@dataclass(frozen=True)
class Bar:
    target_candidate_id: str
    symbol: str
    timestamp: datetime
    available_time: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    bar_vwap: float | None = None
    dollar_volume: float | None = None
    spread_bps: float | None = None


@dataclass(frozen=True)
class ContextRow:
    available_time: datetime
    context_ref: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class OptionChainRow:
    underlying: str
    snapshot_time: datetime
    expiration: str
    option_right_type: str
    strike: float | None
    bid: float | None
    ask: float | None
    mid: float | None
    spread_pct: float | None
    bid_size: float | None
    ask_size: float | None
    implied_vol: float | None
    delta: float | None
    underlying_price: float | None
    days_to_expiration: int | None
    bar_volume: float | None = None
    bar_trade_count: int | None = None
    trade_notional: float | None = None
    open_interest: float | None = None
    open_interest_change: float | None = None


@dataclass(frozen=True)
class TargetStateInputs:
    bars_by_candidate: dict[str, list[Bar]]
    market_context_rows: tuple[ContextRow, ...] = ()
    sector_context_rows: tuple[ContextRow, ...] = ()
    sector_context_symbol_by_candidate: dict[str, str] | None = None
    symbol_by_candidate: dict[str, str] | None = None
    option_overlay_by_candidate: dict[str, bool] | None = None
    option_chain_rows_by_symbol: dict[str, tuple[OptionChainRow, ...]] | None = None


class TargetStateVectorError(ValueError):
    """Raised when target state-vector inputs are invalid."""


@dataclass(frozen=True)
class _ContextTimeline:
    rows: tuple[ContextRow, ...]
    available_times: tuple[datetime, ...]

    def latest_at(self, available_time: datetime) -> ContextRow | None:
        index = bisect_right(self.available_times, available_time) - 1
        return self.rows[index] if index >= 0 else None


@dataclass(frozen=True)
class _OptionSnapshot:
    snapshot_time: datetime
    rows: tuple[OptionChainRow, ...]


@dataclass(frozen=True)
class _OptionRoleSelection:
    rows: tuple[OptionChainRow, ...]
    roles_by_key: dict[tuple[str, str, float | None], set[str]]


@dataclass(frozen=True)
class _OptionChainTimeline:
    snapshots: tuple[_OptionSnapshot, ...]
    snapshot_times: tuple[datetime, ...]

    def latest_at(self, available_time: datetime) -> _OptionSnapshot | None:
        index = bisect_right(self.snapshot_times, available_time) - 1
        return self.snapshots[index] if index >= 0 else None


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [{str(k): str(v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def read_json_rows(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("rows", "bars", "target_candidates", "market_context_rows", "sector_context_rows"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise TargetStateVectorError(f"{path} must contain a JSON list or an object with a rows/bars key")
    return [dict(item) for item in payload]


def build_inputs(
    *,
    bar_rows: Iterable[Mapping[str, Any]],
    candidate_rows: Iterable[Mapping[str, Any]],
    market_context_rows: Iterable[Mapping[str, Any]] = (),
    sector_context_rows: Iterable[Mapping[str, Any]] = (),
    option_chain_rows: Iterable[Mapping[str, Any]] = (),
) -> TargetStateInputs:
    candidates, sector_context_symbol_by_candidate, option_overlay_by_candidate = _candidate_maps(candidate_rows)
    symbol_by_candidate = {target_candidate_id: symbol for symbol, target_candidate_id in candidates.items()}
    bars_by_candidate: dict[str, list[Bar]] = {}
    for row in bar_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        target_candidate_id = str(row.get("target_candidate_id") or "").strip() or candidates.get(symbol, "")
        if not target_candidate_id or not symbol:
            continue
        timestamp = _parse_timestamp(row.get("timestamp") or row.get("available_time"))
        bar = Bar(
            target_candidate_id=target_candidate_id,
            symbol=symbol,
            timestamp=timestamp,
            available_time=_parse_timestamp(row.get("available_time") or timestamp.isoformat()),
            open=_safe_float(row.get("bar_open") or row.get("open")),
            high=_safe_float(row.get("bar_high") or row.get("high")),
            low=_safe_float(row.get("bar_low") or row.get("low")),
            close=_safe_float(row.get("bar_close") or row.get("close")),
            volume=_safe_float(row.get("bar_volume") or row.get("volume")),
            bar_vwap=_safe_float(row.get("bar_vwap") or row.get("vwap")),
            dollar_volume=_safe_float(row.get("dollar_volume")),
            spread_bps=_safe_float(row.get("spread_bps")),
        )
        bars_by_candidate.setdefault(target_candidate_id, []).append(bar)

    if not bars_by_candidate:
        raise TargetStateVectorError("at least one candidate-mapped bar row is required")

    for target_candidate_id, bars in bars_by_candidate.items():
        bars_by_candidate[target_candidate_id] = sorted(bars, key=lambda item: (item.available_time, item.timestamp))

    return TargetStateInputs(
        bars_by_candidate=bars_by_candidate,
        market_context_rows=tuple(_context_rows(market_context_rows, default_prefix="market_context")),
        sector_context_rows=tuple(_context_rows(sector_context_rows, default_prefix="sector_context")),
        sector_context_symbol_by_candidate=sector_context_symbol_by_candidate,
        symbol_by_candidate=symbol_by_candidate,
        option_overlay_by_candidate=option_overlay_by_candidate,
        option_chain_rows_by_symbol=_option_chain_rows_by_symbol(option_chain_rows),
    )


def generate_rows(
    inputs: TargetStateInputs,
    *,
    run_id: str = DEFAULT_RUN_ID,
    target_context_state_version: str = DEFAULT_VECTOR_VERSION,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sector_rows_by_symbol = _sector_rows_by_symbol(inputs.sector_context_rows)
    option_chain_rows_by_symbol = inputs.option_chain_rows_by_symbol or {}
    for target_candidate_id in sorted(inputs.bars_by_candidate):
        symbol = (inputs.symbol_by_candidate or {}).get(target_candidate_id, "")
        option_overlay_enabled = (inputs.option_overlay_by_candidate or {}).get(target_candidate_id, True)
        sector_context_rows = _sector_rows_for_candidate(
            sector_rows_by_symbol,
            (inputs.sector_context_symbol_by_candidate or {}).get(target_candidate_id),
        )
        rows.extend(
            generate_candidate_rows(
                inputs.bars_by_candidate[target_candidate_id],
                inputs.market_context_rows,
                sector_context_rows,
                option_chain_rows_by_symbol.get(symbol, ()),
                run_id=run_id,
                target_context_state_version=target_context_state_version,
                option_overlay_enabled=option_overlay_enabled,
            )
        )
    _attach_peer_ranks(rows)
    return rows


def iter_rows(
    inputs: TargetStateInputs,
    *,
    run_id: str = DEFAULT_RUN_ID,
    target_context_state_version: str = DEFAULT_VECTOR_VERSION,
    emit_start_time: datetime | None = None,
    emit_end_time: datetime | None = None,
) -> Iterable[dict[str, Any]]:
    if len(inputs.bars_by_candidate) != 1:
        for row in generate_rows(inputs, run_id=run_id, target_context_state_version=target_context_state_version):
            available_time = _parse_timestamp(row.get("available_time"))
            if emit_start_time is not None and available_time < emit_start_time:
                continue
            if emit_end_time is not None and available_time >= emit_end_time:
                continue
            yield row
        return
    sector_rows_by_symbol = _sector_rows_by_symbol(inputs.sector_context_rows)
    option_chain_rows_by_symbol = inputs.option_chain_rows_by_symbol or {}
    target_candidate_id = next(iter(inputs.bars_by_candidate))
    symbol = (inputs.symbol_by_candidate or {}).get(target_candidate_id, "")
    option_overlay_enabled = (inputs.option_overlay_by_candidate or {}).get(target_candidate_id, True)
    sector_context_rows = _sector_rows_for_candidate(
        sector_rows_by_symbol,
        (inputs.sector_context_symbol_by_candidate or {}).get(target_candidate_id),
    )
    for row in iter_candidate_rows(
        inputs.bars_by_candidate[target_candidate_id],
        inputs.market_context_rows,
        sector_context_rows,
        option_chain_rows_by_symbol.get(symbol, ()),
        run_id=run_id,
        target_context_state_version=target_context_state_version,
        option_overlay_enabled=option_overlay_enabled,
        emit_start_time=emit_start_time,
        emit_end_time=emit_end_time,
    ):
        _attach_peer_ranks([row])
        yield row


def generate_candidate_rows(
    bars: Sequence[Bar],
    market_context_rows: Sequence[ContextRow] = (),
    sector_context_rows: Sequence[ContextRow] = (),
    option_chain_rows: Sequence[OptionChainRow] = (),
    *,
    run_id: str = DEFAULT_RUN_ID,
    target_context_state_version: str = DEFAULT_VECTOR_VERSION,
    option_overlay_enabled: bool = True,
) -> list[dict[str, Any]]:
    return list(
        iter_candidate_rows(
            bars,
            market_context_rows,
            sector_context_rows,
            option_chain_rows,
            run_id=run_id,
            target_context_state_version=target_context_state_version,
            option_overlay_enabled=option_overlay_enabled,
        )
    )


def iter_candidate_rows(
    bars: Sequence[Bar],
    market_context_rows: Sequence[ContextRow] = (),
    sector_context_rows: Sequence[ContextRow] = (),
    option_chain_rows: Sequence[OptionChainRow] = (),
    *,
    run_id: str = DEFAULT_RUN_ID,
    target_context_state_version: str = DEFAULT_VECTOR_VERSION,
    option_overlay_enabled: bool = True,
    emit_start_time: datetime | None = None,
    emit_end_time: datetime | None = None,
) -> Iterable[dict[str, Any]]:
    market_context_lookup = _context_timeline(market_context_rows)
    sector_context_lookup = _context_timeline(sector_context_rows)
    option_context_lookup = _option_chain_timeline(option_chain_rows)
    closes = [bar.close for bar in bars]
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    volumes = [bar.volume for bar in bars]
    vwaps = [bar.bar_vwap for bar in bars]
    spreads = [bar.spread_bps for bar in bars]
    dollar_volumes = [bar.dollar_volume for bar in bars]
    feature_cache = _TargetRollingFeatures(closes, highs, lows, volumes, vwaps, dollar_volumes)
    option_state_cache: dict[datetime, tuple[dict[str, Any] | None, dict[str, Any]]] = {}

    for index, bar in enumerate(bars):
        if emit_start_time is not None and bar.available_time < emit_start_time:
            continue
        if emit_end_time is not None and bar.available_time >= emit_end_time:
            continue
        market_context = market_context_lookup.latest_at(bar.available_time)
        sector_context = sector_context_lookup.latest_at(bar.available_time)
        option_state: dict[str, Any] | None = None
        option_diagnostics: dict[str, Any] | None = None
        if option_overlay_enabled:
            option_snapshot = option_context_lookup.latest_at(bar.available_time)
            if option_snapshot is None:
                option_state, option_diagnostics = _target_option_chain_state(None)
            else:
                cached_option_state = option_state_cache.get(option_snapshot.snapshot_time)
                if cached_option_state is None:
                    cached_option_state = _target_option_chain_state(option_snapshot)
                    option_state_cache[option_snapshot.snapshot_time] = cached_option_state
                option_state, option_diagnostics = cached_option_state
        target_state = _target_state_features(
            index,
            closes,
            highs,
            lows,
            volumes,
            vwaps,
            spreads,
            dollar_volumes,
            feature_cache=feature_cache,
            option_chain_state=option_state,
            include_option_chain_state=option_overlay_enabled,
        )
        market_state = _market_state_features(market_context)
        sector_state = _sector_state_features(sector_context)
        cross_state = _cross_state_features(target_state, market_state, sector_state)
        yield {
            "run_id": run_id,
            "source_run_ref": run_id,
            "available_time": bar.available_time.isoformat(),
            "tradeable_time": bar.available_time.isoformat(),
            "target_candidate_id": bar.target_candidate_id,
            "market_context_state_ref": market_context.context_ref if market_context else None,
            "sector_context_state_ref": sector_context.context_ref if sector_context else None,
            "target_context_state_version": target_context_state_version,
            "market_state_features": market_state,
            "sector_state_features": sector_state,
            "target_state_features": target_state,
            "cross_state_features": cross_state,
            "feature_quality_diagnostics": _feature_quality(
                index,
                bar,
                market_context,
                sector_context,
                option_diagnostics,
                include_option_chain_diagnostics=option_overlay_enabled,
            ),
        }


def payload_columns(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted({key for row in rows for key in row if key not in METADATA_COLUMNS})


def _candidate_maps(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, str], dict[str, str], dict[str, bool]]:
    candidates: dict[str, str] = {}
    sector_symbols: dict[str, str] = {}
    option_overlay_by_candidate: dict[str, bool] = {}
    for row in rows:
        target_candidate_id = str(row.get("target_candidate_id") or "").strip()
        symbol = str(row.get("symbol") or row.get("routing_symbol_ref") or row.get("audit_symbol_ref") or "").strip().upper()
        if target_candidate_id and symbol:
            candidates[symbol] = target_candidate_id
            sector_symbol = str(row.get("sector_context_symbol") or row.get("sector_or_industry_symbol") or "").strip().upper()
            if sector_symbol:
                sector_symbols[target_candidate_id] = sector_symbol
            option_overlay_by_candidate[target_candidate_id] = _candidate_option_overlay_enabled(row)
    return candidates, sector_symbols, option_overlay_by_candidate


def _candidate_option_overlay_enabled(row: Mapping[str, Any]) -> bool:
    asset_class = str(row.get("target_asset_class") or row.get("asset_class") or row.get("instrument_type") or "").strip().lower()
    option_status = str(
        row.get("optionable_underlying_status")
        or row.get("optionable_proxy_status")
        or row.get("listed_option_status")
        or ""
    ).strip().lower()
    if asset_class in {"crypto_spot", "spot_crypto", "crypto"}:
        return False
    if option_status in {"confirmed_no_listed_options", "no_listed_options", "no_listed_options_or_unverified"}:
        return False
    return True


def _context_timeline(rows: Sequence[ContextRow]) -> _ContextTimeline:
    sorted_rows = tuple(sorted(rows, key=lambda item: item.available_time))
    return _ContextTimeline(sorted_rows, tuple(row.available_time for row in sorted_rows))


def _option_chain_timeline(rows: Sequence[OptionChainRow]) -> _OptionChainTimeline:
    grouped: dict[datetime, list[OptionChainRow]] = {}
    for row in rows:
        grouped.setdefault(row.snapshot_time, []).append(row)
    snapshots = tuple(
        _OptionSnapshot(snapshot_time, tuple(sorted(items, key=lambda item: (item.expiration, item.option_right_type, item.strike or -1.0))))
        for snapshot_time, items in sorted(grouped.items(), key=lambda item: item[0])
    )
    return _OptionChainTimeline(snapshots, tuple(snapshot.snapshot_time for snapshot in snapshots))


def _sector_rows_by_symbol(rows: Sequence[ContextRow]) -> dict[str, tuple[ContextRow, ...]]:
    grouped: dict[str, list[ContextRow]] = {"": []}
    for row in rows:
        symbol = str(row.payload.get("sector_or_industry_symbol") or row.payload.get("symbol") or "").strip().upper()
        grouped.setdefault(symbol, []).append(row)
    return {symbol: tuple(sorted(items, key=lambda item: item.available_time)) for symbol, items in grouped.items()}


def _sector_rows_for_candidate(rows_by_symbol: Mapping[str, tuple[ContextRow, ...]], sector_context_symbol: str | None) -> tuple[ContextRow, ...]:
    if not sector_context_symbol:
        return rows_by_symbol.get("", ())
    symbol = sector_context_symbol.strip().upper()
    return rows_by_symbol.get(symbol) or rows_by_symbol.get("", ())


def _context_rows(rows: Iterable[Mapping[str, Any]], *, default_prefix: str) -> list[ContextRow]:
    output: list[ContextRow] = []
    for index, row in enumerate(rows):
        available_time = _parse_timestamp(row.get("available_time") or row.get("snapshot_time") or row.get("timestamp"))
        context_ref = str(
            row.get("context_ref")
            or row.get("state_ref")
            or row.get("market_context_state_ref")
            or row.get("sector_context_state_ref")
            or row.get("state_id")
            or f"{default_prefix}_{index}"
        )
        payload = {str(key): value for key, value in row.items() if key not in {"available_time", "snapshot_time", "timestamp", "context_ref", "state_ref"}}
        output.append(ContextRow(available_time=available_time, context_ref=context_ref, payload=payload))
    return sorted(output, key=lambda item: item.available_time)


def _option_chain_rows_by_symbol(rows: Iterable[Mapping[str, Any]]) -> dict[str, tuple[OptionChainRow, ...]]:
    grouped: dict[str, list[OptionChainRow]] = {}
    for row in rows:
        underlying = str(row.get("underlying") or row.get("symbol") or "").strip().upper()
        if not underlying:
            continue
        snapshot_time = _parse_timestamp(row.get("snapshot_time") or row.get("available_time") or row.get("timestamp"))
        item = OptionChainRow(
            underlying=underlying,
            snapshot_time=snapshot_time,
            expiration=str(row.get("expiration") or ""),
            option_right_type=str(row.get("option_right_type") or ""),
            strike=_safe_float(row.get("strike")),
            bid=_safe_float(row.get("bid")),
            ask=_safe_float(row.get("ask")),
            mid=_safe_float(row.get("mid")),
            spread_pct=_safe_float(row.get("spread_pct")),
            bid_size=_safe_float(row.get("bid_size")),
            ask_size=_safe_float(row.get("ask_size")),
            implied_vol=_safe_float(row.get("implied_vol")),
            delta=_safe_float(row.get("delta")),
            underlying_price=_safe_float(row.get("underlying_price")),
            days_to_expiration=_safe_int(row.get("days_to_expiration")),
            bar_volume=_safe_float(row.get("bar_volume")),
            bar_trade_count=_safe_int(row.get("bar_trade_count")),
            trade_notional=_safe_float(row.get("trade_notional")),
            open_interest=_safe_float(row.get("open_interest")),
            open_interest_change=_safe_float(row.get("open_interest_change")),
        )
        grouped.setdefault(underlying, []).append(item)
    return {symbol: tuple(sorted(items, key=lambda item: (item.snapshot_time, item.expiration, item.option_right_type, item.strike or -1.0))) for symbol, items in grouped.items()}


def _latest_context(rows: Sequence[ContextRow], available_time: datetime) -> ContextRow | None:
    latest = None
    for row in rows:
        if row.available_time <= available_time:
            latest = row
        else:
            break
    return latest


def _market_state_features(context: ContextRow | None) -> dict[str, Any]:
    return _project_context(
        context,
        groups=(
            "market_regime_state",
            "market_trend_state",
            "market_volatility_state",
            "market_breadth_state",
            "market_liquidity_stress_state",
            "market_correlation_state",
        ),
        default_key="market_context_payload",
    )


def _sector_state_features(context: ContextRow | None) -> dict[str, Any]:
    return _project_context(
        context,
        groups=(
            "sector_context_state",
            "sector_relative_direction_state",
            "sector_trend_quality_stability_state",
            "sector_volatility_state",
            "sector_breadth_dispersion_state",
            "sector_liquidity_tradability_state",
        ),
        default_key="sector_context_payload",
    )


def _project_context(context: ContextRow | None, *, groups: Sequence[str], default_key: str) -> dict[str, Any]:
    projected: dict[str, Any] = {
        "state_observation_windows": list(STATE_WINDOW_LABELS),
        "state_window_sync_policy": STATE_WINDOW_SYNC_POLICY,
        "multi_frame_state": {},
    }
    if context is None:
        projected.update({group: None for group in groups})
        projected[default_key] = {}
        projected["multi_frame_state"] = {label: {} for label in STATE_WINDOW_LABELS}
        return projected
    payload = dict(context.payload)
    projected.update({group: payload.get(group) for group in groups})
    projected[default_key] = {key: value for key, value in payload.items() if key not in groups}
    projected["multi_frame_state"] = _context_multi_frame_state(payload)
    return projected


def _context_multi_frame_state(payload: Mapping[str, Any]) -> dict[str, dict[str, float | None]]:
    frames: dict[str, dict[str, float | None]] = {}
    for label, window in STATE_WINDOW_MINUTES.items():
        frames[label] = {
            "return": _first_float(payload, f"return_{label}", f"market_return_{label}", f"sector_return_{label}"),
            "direction_score": _first_float(payload, f"direction_score_{label}", f"1_market_direction_score_{label}", f"2_sector_relative_direction_score_{label}"),
            "volatility": _first_float(payload, f"realized_vol_{label}", f"market_volatility_{label}", f"sector_volatility_{label}"),
            "trend_quality": _first_float(payload, f"trend_quality_{label}", f"1_trend_quality_score_{label}", f"2_sector_trend_quality_score_{label}"),
            "liquidity_tradability": _first_float(payload, f"liquidity_tradability_{label}", "2_sector_liquidity_tradability_score"),
            "observation_minutes": float(window),
        }
    return frames


class _TargetRollingFeatures:
    def __init__(
        self,
        closes: Sequence[float | None],
        highs: Sequence[float | None],
        lows: Sequence[float | None],
        volumes: Sequence[float | None],
        vwaps: Sequence[float | None],
        dollar_volumes: Sequence[float | None],
    ) -> None:
        self.closes = closes
        self.highs = highs
        self.lows = lows
        self.volumes = volumes
        self.vwaps = vwaps
        self.dollar_volumes = dollar_volumes
        self.simple_returns, self.log_returns = self._return_series(closes)
        self.return_positions, self.return_signs, self.return_run_lengths, self.return_flip_prefix = self._valid_return_index(self.simple_returns)
        self.return_abs_prefix = self._prefix_over_valid(self.simple_returns, absolute=True)
        self.return_sum_prefix = self._prefix_over_valid(self.simple_returns)
        self.return_sumsq_prefix = self._prefix_over_valid(self.simple_returns, square=True)
        self.true_ranges = self._true_range_series(closes, highs, lows)
        self.session_open = self._rolling_first(closes, 390)
        self.session_high = self._rolling_max(highs, 390)
        self.session_low = self._rolling_min(lows, 390)
        self.window_highs = {window: self._rolling_max(highs, window) for window in STATE_WINDOW_MINUTES.values()}
        self.window_lows = {window: self._rolling_min(lows, window) for window in STATE_WINDOW_MINUTES.values()}
        self.volume_positions, self.volume_prefix = self._valid_value_prefix(volumes)
        self.dollar_volume_positions, self.dollar_volume_prefix = self._valid_value_prefix(dollar_volumes)
        self.true_range_positions, self.true_range_prefix = self._valid_value_prefix(self.true_ranges)
        self.log_return_positions, self.log_return_prefix, self.log_return_sumsq_prefix = self._valid_value_prefix_with_squares(self.log_returns)

    @staticmethod
    def _return_series(values: Sequence[float | None]) -> tuple[list[float | None], list[float | None]]:
        simple: list[float | None] = [None] * len(values)
        logs: list[float | None] = [None] * len(values)
        for index in range(1, len(values)):
            current = values[index]
            previous = values[index - 1]
            if current is None or previous in (None, 0):
                continue
            simple[index] = current / previous - 1.0
            logs[index] = math.log(current / previous)
        return simple, logs

    @staticmethod
    def _true_range_series(closes: Sequence[float | None], highs: Sequence[float | None], lows: Sequence[float | None]) -> list[float | None]:
        true_ranges: list[float | None] = [None] * len(closes)
        for index in range(1, len(closes)):
            high = highs[index]
            low = lows[index]
            if high is None or low is None:
                continue
            previous_close = closes[index - 1]
            value = high - low
            if previous_close is not None:
                value = max(value, abs(high - previous_close), abs(low - previous_close))
            true_ranges[index] = value
        return true_ranges

    @staticmethod
    def _rolling_first(values: Sequence[float | None], window: int) -> list[float | None]:
        output: list[float | None] = []
        valid_indexes: deque[int] = deque()
        for index, value in enumerate(values):
            if value is not None:
                valid_indexes.append(index)
            start = max(0, index - window + 1)
            while valid_indexes and valid_indexes[0] < start:
                valid_indexes.popleft()
            output.append(values[valid_indexes[0]] if valid_indexes else None)
        return output

    @staticmethod
    def _rolling_max(values: Sequence[float | None], window: int) -> list[float | None]:
        output: list[float | None] = []
        indexes: deque[int] = deque()
        for index, value in enumerate(values):
            if value is not None:
                while indexes and values[indexes[-1]] is not None and float(values[indexes[-1]]) <= float(value):
                    indexes.pop()
                indexes.append(index)
            start = max(0, index - window + 1)
            while indexes and indexes[0] < start:
                indexes.popleft()
            output.append(values[indexes[0]] if indexes else None)
        return output

    @staticmethod
    def _rolling_min(values: Sequence[float | None], window: int) -> list[float | None]:
        output: list[float | None] = []
        indexes: deque[int] = deque()
        for index, value in enumerate(values):
            if value is not None:
                while indexes and values[indexes[-1]] is not None and float(values[indexes[-1]]) >= float(value):
                    indexes.pop()
                indexes.append(index)
            start = max(0, index - window + 1)
            while indexes and indexes[0] < start:
                indexes.popleft()
            output.append(values[indexes[0]] if indexes else None)
        return output

    @staticmethod
    def _valid_value_prefix(values: Sequence[float | None]) -> tuple[list[int], list[float]]:
        positions: list[int] = []
        prefix: list[float] = [0.0]
        for index, value in enumerate(values):
            if value is None:
                continue
            positions.append(index)
            prefix.append(prefix[-1] + float(value))
        return positions, prefix

    @staticmethod
    def _valid_value_prefix_with_squares(values: Sequence[float | None]) -> tuple[list[int], list[float], list[float]]:
        positions: list[int] = []
        prefix: list[float] = [0.0]
        sumsq_prefix: list[float] = [0.0]
        for index, value in enumerate(values):
            if value is None:
                continue
            number = float(value)
            positions.append(index)
            prefix.append(prefix[-1] + number)
            sumsq_prefix.append(sumsq_prefix[-1] + number * number)
        return positions, prefix, sumsq_prefix

    @staticmethod
    def _valid_return_index(values: Sequence[float | None]) -> tuple[list[int], list[int], list[int], list[int]]:
        positions: list[int] = []
        signs: list[int] = []
        run_lengths: list[int] = []
        flip_prefix: list[int] = [0]
        for index, value in enumerate(values):
            if value is None:
                continue
            sign = 1 if value > 0 else -1 if value < 0 else 0
            positions.append(index)
            signs.append(sign)
            if len(signs) == 1:
                run_lengths.append(1)
                flip_prefix.append(0)
                continue
            previous_sign = signs[-2]
            run_lengths.append(run_lengths[-1] + 1 if sign == previous_sign else 1)
            flip_increment = 1 if sign and previous_sign and sign != previous_sign else 0
            flip_prefix.append(flip_prefix[-1] + flip_increment)
        return positions, signs, run_lengths, flip_prefix

    def _prefix_over_valid(self, values: Sequence[float | None], *, absolute: bool = False, square: bool = False) -> list[float]:
        prefix: list[float] = [0.0]
        for position in self.return_positions:
            value = float(values[position] or 0.0)
            if absolute:
                value = abs(value)
            if square:
                value = value * value
            prefix.append(prefix[-1] + value)
        return prefix

    def _valid_range(self, positions: Sequence[int], start: int, end: int) -> tuple[int, int]:
        left = bisect_left(positions, start)
        right = bisect_right(positions, end)
        return left, right

    def _time_range(self, index: int, window: int) -> tuple[int, int]:
        return max(1, index - window + 1), index

    def window_return(self, index: int, window: int) -> float | None:
        if index < window:
            return None
        current = self.closes[index]
        previous = self.closes[index - window]
        if current is None or previous in (None, 0):
            return None
        return current / previous - 1

    def realized_vol(self, index: int, window: int) -> float | None:
        start, end = self._time_range(index, window)
        left, right = self._valid_range(self.log_return_positions, start, end)
        count = right - left
        if count < 2:
            return None
        total = self.log_return_prefix[right] - self.log_return_prefix[left]
        sumsq = self.log_return_sumsq_prefix[right] - self.log_return_sumsq_prefix[left]
        return _pstdev_from_sums(total, sumsq, count)

    def range_position(self, index: int, window: int) -> float | None:
        close = self.closes[index]
        high = self.window_highs[window][index]
        low = self.window_lows[window][index]
        if close is None or high is None or low is None or high == low:
            return None
        return (close - low) / (high - low)

    def atr_pct(self, index: int, window: int) -> float | None:
        close = self.closes[index]
        if close in (None, 0) or index < 1:
            return None
        start, end = self._time_range(index, window)
        left, right = self._valid_range(self.true_range_positions, start, end)
        count = right - left
        if count == 0:
            return None
        return ((self.true_range_prefix[right] - self.true_range_prefix[left]) / count) / close

    def relative_to_window(self, values_name: str, index: int, window: int) -> float | None:
        if values_name == "volume":
            values = self.volumes
            positions = self.volume_positions
            prefix = self.volume_prefix
        else:
            values = self.dollar_volumes
            positions = self.dollar_volume_positions
            prefix = self.dollar_volume_prefix
        current = values[index]
        if current is None:
            return None
        start = max(0, index - window + 1)
        left, right = self._valid_range(positions, start, index)
        count = right - left
        if count == 0:
            return None
        avg = (prefix[right] - prefix[left]) / count
        return None if avg == 0 else current / avg

    def return_stats(self, index: int, window: int) -> tuple[int, float, float, float]:
        start, end = self._time_range(index, window)
        left, right = self._valid_range(self.return_positions, start, end)
        count = right - left
        total = self.return_sum_prefix[right] - self.return_sum_prefix[left]
        abs_total = self.return_abs_prefix[right] - self.return_abs_prefix[left]
        sumsq = self.return_sumsq_prefix[right] - self.return_sumsq_prefix[left]
        return count, total, abs_total, sumsq

    def direction_flip_count(self, index: int, window: int) -> int | None:
        start, end = self._time_range(index, window)
        left, right = self._valid_range(self.return_positions, start, end)
        if right - left < 2:
            return None
        return self.return_flip_prefix[right] - self.return_flip_prefix[left + 1]

    def trend_age_bars(self, index: int, window: int) -> int | None:
        start, end = self._time_range(index, window)
        left, right = self._valid_range(self.return_positions, start, end)
        if right <= left:
            return None
        sign = self.return_signs[right - 1]
        if sign == 0:
            return 0
        return min(self.return_run_lengths[right - 1], right - left)

    def state_persistence_score(self, index: int, window: int) -> float | None:
        age = self.trend_age_bars(index, window)
        if age is None:
            return None
        return min(age / max(window, 1), 1.0)

    def time_since_last_direction_flip(self, index: int) -> int | None:
        start, end = self._time_range(index, min(index + 1, STATE_WINDOW_MINUTES["1W"]))
        left, right = self._valid_range(self.return_positions, start, end)
        if right - left < 2:
            return None
        for position in range(right - 1, left, -1):
            if self.return_signs[position] and self.return_signs[position - 1] and self.return_signs[position] != self.return_signs[position - 1]:
                return right - position
        return right - left

    def path_stability_score(self, index: int, window: int) -> float | None:
        count, total, abs_total, sumsq = self.return_stats(index, window)
        if count < 2:
            return None
        efficiency = None if abs_total == 0 else abs(total) / abs_total
        flips = self.direction_flip_count(index, window)
        flip_penalty = None if flips is None else 1.0 - min(flips / max(count - 1, 1), 1.0)
        vol = _pstdev_from_sums(total, sumsq, count)
        vol_stability = None if vol is None else 1.0 - min(vol / 0.02, 1.0)
        return _average([efficiency, flip_penalty, vol_stability])

    def momentum_decay_score(self, index: int, window: int) -> float | None:
        left, right = self._valid_range(self.return_positions, *self._time_range(index, window))
        count = right - left
        if count < 4:
            return None
        midpoint = left + count // 2
        first_count = midpoint - left
        second_count = right - midpoint
        first = (self.return_abs_prefix[midpoint] - self.return_abs_prefix[left]) / first_count
        second = (self.return_abs_prefix[right] - self.return_abs_prefix[midpoint]) / second_count
        return None if first == 0 else max(0.0, min((first - second) / first, 1.0))

    def volume_exhaustion_score(self, index: int, window: int) -> float | None:
        current = self.volumes[index]
        if current is None:
            return None
        start = max(0, index - window + 1)
        left, right = self._valid_range(self.volume_positions, start, index)
        count = right - left
        if count < 4:
            return None
        midpoint = left + count // 2
        first_count = midpoint - left
        second_count = right - midpoint
        first = (self.volume_prefix[midpoint] - self.volume_prefix[left]) / first_count
        second = (self.volume_prefix[right] - self.volume_prefix[midpoint]) / second_count
        return None if first == 0 else max(0.0, min((first - second) / first, 1.0))

    def volatility_exhaustion_score(self, index: int, window: int) -> float | None:
        left, right = self._valid_range(self.return_positions, *self._time_range(index, window))
        count = right - left
        if count < 4:
            return None
        midpoint = left + count // 2
        first_count = midpoint - left
        second_count = right - midpoint
        first = _pstdev_from_sums(
            self.return_sum_prefix[midpoint] - self.return_sum_prefix[left],
            self.return_sumsq_prefix[midpoint] - self.return_sumsq_prefix[left],
            first_count,
        )
        second = _pstdev_from_sums(
            self.return_sum_prefix[right] - self.return_sum_prefix[midpoint],
            self.return_sumsq_prefix[right] - self.return_sumsq_prefix[midpoint],
            second_count,
        )
        if first in (None, 0) or second is None:
            return None
        return max(0.0, min((second - first) / first, 1.0))

    def late_trend_risk_score(self, index: int, window: int) -> float | None:
        return _average([
            self.state_persistence_score(index, window),
            self.momentum_decay_score(index, window),
            self.volume_exhaustion_score(index, window),
            self.volatility_exhaustion_score(index, window),
        ])


def _target_option_chain_state(snapshot: _OptionSnapshot | None) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if snapshot is None:
        return None, {"has_option_chain_source": False}
    rows = list(snapshot.rows)
    stable_core = _select_stable_option_core(rows)
    short_overlay = _select_short_expiry_overlay(rows)
    stable_state_rows = _rows_with_role_suffix(stable_core, (":atm_state", ":canonical_wing_state"))
    activity_rows = _rows_with_role_suffix(stable_core, (":round_activity_attention", ":oi_activity_attention"))
    short_rows = list(short_overlay.rows)
    selected_rows_by_key = {_option_row_key(row): row for row in (*stable_core.rows, *short_overlay.rows)}
    front_atm_iv = _median(row.implied_vol for row in _rows_with_role_prefix(stable_core, "front:atm_state") if row.implied_vol is not None)
    near_atm_iv = _median(row.implied_vol for row in _rows_with_role_prefix(stable_core, "near:atm_state") if row.implied_vol is not None)
    mid_atm_iv = _median(row.implied_vol for row in _rows_with_role_prefix(stable_core, "mid:atm_state") if row.implied_vol is not None)
    canonical_wings = _rows_with_role_suffix(stable_core, (":canonical_wing_state",))
    call_wing_iv = _median(row.implied_vol for row in canonical_wings if row.option_right_type.upper().startswith("C") and row.implied_vol is not None)
    put_wing_iv = _median(row.implied_vol for row in canonical_wings if row.option_right_type.upper().startswith("P") and row.implied_vol is not None)
    quote_rows = [row for row in stable_state_rows if _has_quote(row)]
    spread_values = [row.spread_pct for row in quote_rows if row.spread_pct is not None]
    depth_values = [(row.bid_size or 0.0) + (row.ask_size or 0.0) for row in quote_rows if row.bid_size is not None or row.ask_size is not None]
    volume_call = sum(row.bar_volume or 0.0 for row in activity_rows if row.option_right_type.upper().startswith("C"))
    volume_put = sum(row.bar_volume or 0.0 for row in activity_rows if row.option_right_type.upper().startswith("P"))
    trade_count_call = sum(row.bar_trade_count or 0 for row in activity_rows if row.option_right_type.upper().startswith("C"))
    trade_count_put = sum(row.bar_trade_count or 0 for row in activity_rows if row.option_right_type.upper().startswith("P"))
    short_atm_rows = _rows_with_role_suffix(short_overlay, (":atm_pressure",))
    short_atm_iv = _median(row.implied_vol for row in short_atm_rows if row.implied_vol is not None)
    short_call_volume = sum(row.bar_volume or 0.0 for row in short_rows if row.option_right_type.upper().startswith("C"))
    short_put_volume = sum(row.bar_volume or 0.0 for row in short_rows if row.option_right_type.upper().startswith("P"))
    short_call_trades = sum(row.bar_trade_count or 0 for row in short_rows if row.option_right_type.upper().startswith("C"))
    short_put_trades = sum(row.bar_trade_count or 0 for row in short_rows if row.option_right_type.upper().startswith("P"))
    state = {
        "target_option_liquidity_state": {
            "liquidity_state": _liquidity_state(_median(spread_values), _median(depth_values)),
            "quote_depth_state": _depth_state(_median(depth_values)),
            "spread_state": _spread_state(_median(spread_values)),
            "measurement_policy": "selected_stable_core_contract_roles",
        },
        "target_iv_pressure_state": {
            "iv_pressure_state": _iv_pressure_state(front_atm_iv),
            "baseline_policy": "rolling_baseline_pending_uses_absolute_pressure_until_baseline_is_available",
            "measurement_policy": "front_bucket_selected_atm_roles",
        },
        "target_option_skew_pressure_state": {
            "skew_pressure_state": _skew_state(None if put_wing_iv is None or call_wing_iv is None else put_wing_iv - call_wing_iv),
            "measurement_policy": "canonical_delta_wing_pair_with_moneyness_fallback",
        },
        "target_option_term_structure_pressure_state": {
            "term_structure_pressure_state": _term_state(front_atm_iv, near_atm_iv, mid_atm_iv),
            "measurement_policy": "selected_atm_roles_across_front_near_mid_buckets",
        },
        "target_option_flow_pressure_state": {
            "flow_pressure_state": _flow_state(volume_call, volume_put, trade_count_call, trade_count_put),
            "flow_baseline_policy": "rolling_baseline_pending_uses_selected_activity_attention_call_put_balance",
            "measurement_policy": "selected_activity_attention_roles_not_broad_chain_flow",
        },
        "target_short_expiry_pressure_overlay": {
            "short_expiry_overlay_state": "available" if short_rows else "not_available",
            "short_iv_pressure_state": _iv_pressure_state(short_atm_iv),
            "short_activity_attention_state": _flow_state(short_call_volume, short_put_volume, short_call_trades, short_put_trades),
            "measurement_policy": "zero_to_six_dte_overlay_separate_from_stable_core",
        },
    }
    stable_bucket_rows = [row for row in rows if _stable_option_bucket(row.days_to_expiration) is not None]
    selected_rows = list(selected_rows_by_key.values())
    diagnostics = {
        "has_option_chain_source": True,
        "option_source": "ThetaData",
        "option_chain_snapshot_time": snapshot.snapshot_time.isoformat(),
        "option_contract_row_count": len(rows),
        "option_canonical_contract_row_count": len(stable_bucket_rows),
        "option_selected_contract_row_count": len(selected_rows),
        "option_stable_core_selected_contract_row_count": len(stable_core.rows),
        "option_short_overlay_selected_contract_row_count": len(short_overlay.rows),
        "option_short_dte_contract_row_count": sum(1 for row in rows if _expiry_bucket(row.days_to_expiration) == "short"),
        "option_quote_available_ratio": _ratio(sum(1 for row in selected_rows if _has_quote(row)), len(selected_rows)),
        "option_trade_available_ratio": _ratio(sum(1 for row in selected_rows if (row.bar_volume or 0) > 0 or (row.bar_trade_count or 0) > 0), len(selected_rows)),
        "option_iv_available_ratio": _ratio(sum(1 for row in selected_rows if row.implied_vol is not None), len(selected_rows)),
        "option_greeks_available_ratio": _ratio(sum(1 for row in selected_rows if row.delta is not None), len(selected_rows)),
        "option_chain_observability_score": _average([
            _ratio(sum(1 for row in selected_rows if _has_quote(row)), len(selected_rows)),
            _ratio(sum(1 for row in selected_rows if row.implied_vol is not None), len(selected_rows)),
            _ratio(sum(1 for row in selected_rows if row.delta is not None), len(selected_rows)),
        ]),
        "option_liquidity_quality_score": _liquidity_quality_score(_median(spread_values), _median(depth_values)),
        "option_bucket_counts": {
            bucket: sum(1 for row in rows if _expiry_bucket(row.days_to_expiration) == bucket)
            for bucket in ("short", "front", "near", "mid", "long", "outside")
        },
        "option_selected_role_counts": _role_counts(stable_core, short_overlay),
        "option_role_bucket_coverage": {
            bucket: _role_bucket_available(stable_core, bucket)
            for bucket in ("front", "near", "mid")
        },
        "option_activity_attention_policy": "round_strike_and_point_in_time_open_interest_when_available_same_snapshot_activity_is_validation_only",
        "option_chain_state_reduction_policy": "target_option_contract_role_selector_stable_core_activity_attention_short_overlay",
    }
    return state, diagnostics


def _option_row_key(row: OptionChainRow) -> tuple[str, str, float | None]:
    return (row.expiration, row.option_right_type.upper(), row.strike)


def _add_option_role(
    selected: dict[tuple[str, str, float | None], OptionChainRow],
    roles: dict[tuple[str, str, float | None], set[str]],
    row: OptionChainRow | None,
    role: str,
) -> None:
    if row is None:
        return
    key = _option_row_key(row)
    selected[key] = row
    roles.setdefault(key, set()).add(role)


def _moneyness_log(row: OptionChainRow) -> float | None:
    if row.strike in (None, 0) or row.underlying_price in (None, 0):
        return None
    return math.log(float(row.strike) / float(row.underlying_price))


def _moneyness_sort_value(row: OptionChainRow) -> float:
    value = _moneyness_log(row)
    return 999.0 if value is None else value


def _right_prefix(row: OptionChainRow) -> str:
    return row.option_right_type.upper()[:1]


def _stable_option_bucket(days_to_expiration: int | None) -> str | None:
    if days_to_expiration is None:
        return None
    if 7 <= days_to_expiration <= 45:
        return "front"
    if 46 <= days_to_expiration <= 90:
        return "near"
    if 91 <= days_to_expiration <= 180:
        return "mid"
    return None


def _selected_expiry_by_bucket(rows: Sequence[OptionChainRow], buckets: Sequence[str]) -> dict[str, str]:
    by_bucket: dict[str, dict[str, list[OptionChainRow]]] = {bucket: {} for bucket in buckets}
    for row in rows:
        bucket = _stable_option_bucket(row.days_to_expiration)
        if bucket not in by_bucket:
            continue
        by_bucket[bucket].setdefault(row.expiration, []).append(row)
    selected: dict[str, str] = {}
    for bucket, expiries in by_bucket.items():
        viable: list[tuple[int, int, str]] = []
        for expiration, expiry_rows in expiries.items():
            sides = {_right_prefix(row) for row in expiry_rows if _right_prefix(row) in {"C", "P"}}
            dtes = [row.days_to_expiration for row in expiry_rows if row.days_to_expiration is not None]
            if {"C", "P"}.issubset(sides) and dtes:
                viable.append((min(dtes), -len(expiry_rows), expiration))
        if viable:
            viable.sort()
            selected[bucket] = viable[0][2]
    return selected


def _selected_short_expiry(rows: Sequence[OptionChainRow]) -> str | None:
    expiries: dict[str, list[OptionChainRow]] = {}
    for row in rows:
        if _expiry_bucket(row.days_to_expiration) == "short":
            expiries.setdefault(row.expiration, []).append(row)
    viable: list[tuple[int, int, str]] = []
    for expiration, expiry_rows in expiries.items():
        sides = {_right_prefix(row) for row in expiry_rows if _right_prefix(row) in {"C", "P"}}
        dtes = [row.days_to_expiration for row in expiry_rows if row.days_to_expiration is not None]
        if {"C", "P"}.issubset(sides) and dtes:
            viable.append((min(dtes), -len(expiry_rows), expiration))
    if not viable:
        return None
    viable.sort()
    return viable[0][2]


def _nearest_moneyness(rows: Sequence[OptionChainRow], target: float) -> OptionChainRow | None:
    candidates = [row for row in rows if _moneyness_log(row) is not None]
    if not candidates:
        return None
    candidates.sort(key=lambda row: (abs(_moneyness_sort_value(row) - target), row.strike or 0.0))
    return candidates[0]


def _roundness_score(strike: float | None) -> int:
    if strike is None:
        return 0
    if abs(strike - round(strike)) > 1e-6:
        return 0
    if abs(strike % 10) < 1e-6:
        return 4
    if abs(strike % 5) < 1e-6:
        return 3
    return 2


def _choose_canonical_wing(rows: Sequence[OptionChainRow], side: str) -> OptionChainRow | None:
    if side == "C":
        delta_rows = [row for row in rows if row.delta is not None and 0.20 <= row.delta <= 0.35]
        if delta_rows:
            delta_rows.sort(key=lambda row: (abs(float(row.delta or 0.0) - 0.25), abs(_moneyness_sort_value(row)), row.strike or 0.0))
            return delta_rows[0]
        return _nearest_moneyness([row for row in rows if _right_prefix(row) == "C"], 0.05)
    delta_rows = [row for row in rows if row.delta is not None and -0.35 <= row.delta <= -0.20]
    if delta_rows:
        delta_rows.sort(key=lambda row: (abs(float(row.delta or 0.0) + 0.25), abs(_moneyness_sort_value(row)), row.strike or 0.0))
        return delta_rows[0]
    return _nearest_moneyness([row for row in rows if _right_prefix(row) == "P"], -0.05)


def _choose_round_activity(rows: Sequence[OptionChainRow], side: str) -> OptionChainRow | None:
    candidates = [row for row in rows if _right_prefix(row) == side and _roundness_score(row.strike) > 0]
    if not candidates:
        return None
    candidates.sort(key=lambda row: (-_roundness_score(row.strike), abs(_moneyness_sort_value(row)), row.strike or 0.0))
    return candidates[0]


def _choose_oi_activity(rows: Sequence[OptionChainRow], side: str) -> OptionChainRow | None:
    candidates = [row for row in rows if _right_prefix(row) == side and row.open_interest is not None]
    if not candidates:
        return None
    candidates.sort(key=lambda row: (-(row.open_interest or 0.0), abs(_moneyness_sort_value(row)), row.strike or 0.0))
    return candidates[0]


def _select_stable_option_core(rows: Sequence[OptionChainRow]) -> _OptionRoleSelection:
    selected: dict[tuple[str, str, float | None], OptionChainRow] = {}
    roles: dict[tuple[str, str, float | None], set[str]] = {}
    expiries = _selected_expiry_by_bucket(rows, ("front", "near", "mid"))
    for bucket, expiration in expiries.items():
        bucket_rows = [row for row in rows if row.expiration == expiration and _stable_option_bucket(row.days_to_expiration) == bucket]
        for side in ("C", "P"):
            side_rows = [row for row in bucket_rows if _right_prefix(row) == side]
            _add_option_role(selected, roles, _nearest_moneyness(side_rows, 0.0), f"{bucket}:atm_state")
            _add_option_role(selected, roles, _choose_canonical_wing(side_rows, side), f"{bucket}:canonical_wing_state")
            bounded = [
                row for row in side_rows
                if _moneyness_log(row) is not None
                and ((side == "C" and -0.05 <= _moneyness_sort_value(row) <= 0.12) or (side == "P" and -0.12 <= _moneyness_sort_value(row) <= 0.05))
            ]
            _add_option_role(selected, roles, _choose_round_activity(bounded, side), f"{bucket}:round_activity_attention")
            _add_option_role(selected, roles, _choose_oi_activity(bounded, side), f"{bucket}:oi_activity_attention")
    return _OptionRoleSelection(tuple(selected.values()), roles)


def _select_short_expiry_overlay(rows: Sequence[OptionChainRow]) -> _OptionRoleSelection:
    selected: dict[tuple[str, str, float | None], OptionChainRow] = {}
    roles: dict[tuple[str, str, float | None], set[str]] = {}
    expiration = _selected_short_expiry(rows)
    if expiration is None:
        return _OptionRoleSelection((), {})
    bucket_rows = [row for row in rows if row.expiration == expiration and _expiry_bucket(row.days_to_expiration) == "short"]
    for side in ("C", "P"):
        side_rows = [row for row in bucket_rows if _right_prefix(row) == side]
        _add_option_role(selected, roles, _nearest_moneyness(side_rows, 0.0), "short:atm_pressure")
        _add_option_role(selected, roles, _choose_round_activity(side_rows, side), "short:round_activity_attention")
        _add_option_role(selected, roles, _choose_oi_activity(side_rows, side), "short:oi_activity_attention")
    return _OptionRoleSelection(tuple(selected.values()), roles)


def _rows_with_role_suffix(selection: _OptionRoleSelection, suffixes: Sequence[str]) -> list[OptionChainRow]:
    return [
        row
        for row in selection.rows
        if any(role.endswith(suffix) for role in selection.roles_by_key.get(_option_row_key(row), set()) for suffix in suffixes)
    ]


def _rows_with_role_prefix(selection: _OptionRoleSelection, prefix: str) -> list[OptionChainRow]:
    return [
        row
        for row in selection.rows
        if any(role.startswith(prefix) for role in selection.roles_by_key.get(_option_row_key(row), set()))
    ]


def _role_counts(*selections: _OptionRoleSelection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for selection in selections:
        for roles in selection.roles_by_key.values():
            for role in roles:
                counts[role] = counts.get(role, 0) + 1
    return dict(sorted(counts.items()))


def _role_bucket_available(selection: _OptionRoleSelection, bucket: str) -> dict[str, bool]:
    roles = {role for role_set in selection.roles_by_key.values() for role in role_set if role.startswith(f"{bucket}:")}
    return {
        "atm_call": any(role == f"{bucket}:atm_state" and _right_prefix(row) == "C" for row in selection.rows for role in selection.roles_by_key.get(_option_row_key(row), set())),
        "atm_put": any(role == f"{bucket}:atm_state" and _right_prefix(row) == "P" for row in selection.rows for role in selection.roles_by_key.get(_option_row_key(row), set())),
        "canonical_call_wing": any(role == f"{bucket}:canonical_wing_state" and _right_prefix(row) == "C" for row in selection.rows for role in selection.roles_by_key.get(_option_row_key(row), set())),
        "canonical_put_wing": any(role == f"{bucket}:canonical_wing_state" and _right_prefix(row) == "P" for row in selection.rows for role in selection.roles_by_key.get(_option_row_key(row), set())),
        "activity_attention": any(role.endswith(":round_activity_attention") or role.endswith(":oi_activity_attention") for role in roles),
    }


def _expiry_bucket(days_to_expiration: int | None) -> str:
    if days_to_expiration is None:
        return "outside"
    if 0 <= days_to_expiration <= 6:
        return "short"
    if 7 <= days_to_expiration <= 45:
        return "front"
    if 46 <= days_to_expiration <= 90:
        return "near"
    if 91 <= days_to_expiration <= 180:
        return "mid"
    if 181 <= days_to_expiration <= 365:
        return "long"
    return "outside"


def _moneyness_bucket(row: OptionChainRow) -> str | None:
    delta = row.delta
    right = row.option_right_type.upper()
    if delta is not None:
        if 0.45 <= abs(delta) <= 0.55:
            return "atm"
        if right.startswith("C") and 0.20 <= delta <= 0.35:
            return "otm_call_wing"
        if right.startswith("P") and -0.35 <= delta <= -0.20:
            return "otm_put_wing"
    if row.strike not in (None, 0) and row.underlying_price not in (None, 0):
        if abs(math.log(float(row.strike) / float(row.underlying_price))) <= 0.03:
            return "atm"
    return None


def _has_quote(row: OptionChainRow) -> bool:
    return row.bid is not None and row.ask is not None and row.ask >= row.bid and (row.mid is not None or row.ask > 0)


def _median(values: Iterable[float | int | None]) -> float | None:
    clean = sorted(float(value) for value in values if value is not None)
    if not clean:
        return None
    midpoint = len(clean) // 2
    if len(clean) % 2:
        return clean[midpoint]
    return (clean[midpoint - 1] + clean[midpoint]) / 2


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator <= 0 else numerator / denominator


def _spread_state(spread_pct: float | None) -> str | None:
    if spread_pct is None:
        return None
    if spread_pct <= 0.05:
        return "tight"
    if spread_pct <= 0.15:
        return "normal"
    if spread_pct <= 0.35:
        return "wide"
    return "stressed"


def _depth_state(depth: float | None) -> str | None:
    if depth is None:
        return None
    if depth >= 200:
        return "deep"
    if depth >= 40:
        return "normal"
    if depth > 0:
        return "thin"
    return "missing"


def _liquidity_quality_score(spread_pct: float | None, depth: float | None) -> float | None:
    spread_score = None if spread_pct is None else max(0.0, 1.0 - min(spread_pct / 0.35, 1.0))
    depth_score = None if depth is None else min(math.log10(max(depth, 1.0)) / 3.0, 1.0)
    return _average([spread_score, depth_score])


def _liquidity_state(spread_pct: float | None, depth: float | None) -> str | None:
    score = _liquidity_quality_score(spread_pct, depth)
    if score is None:
        return None
    if score >= 0.75:
        return "deep"
    if score >= 0.45:
        return "normal"
    if score >= 0.20:
        return "thin"
    return "stressed"


def _iv_pressure_state(front_atm_iv: float | None) -> str | None:
    if front_atm_iv is None:
        return None
    if front_atm_iv >= 0.75:
        return "extreme_high"
    if front_atm_iv >= 0.45:
        return "high"
    if front_atm_iv <= 0.15:
        return "low"
    return "normal"


def _skew_state(skew: float | None) -> str | None:
    if skew is None:
        return None
    if skew >= 0.12:
        return "extreme_put_skew"
    if skew >= 0.04:
        return "put_skew"
    if skew <= -0.04:
        return "call_skew"
    return "balanced"


def _term_state(front: float | None, near: float | None, mid: float | None) -> str | None:
    if front is None or near is None:
        return None
    slope = front - near
    if slope >= 0.08:
        return "front_rich"
    if slope <= -0.08:
        return "upward_sloping"
    if mid is not None and near - mid >= 0.08:
        return "near_rich"
    return "flat"


def _flow_state(call_volume: float, put_volume: float, call_trades: int, put_trades: int) -> str | None:
    call_activity = call_volume + call_trades
    put_activity = put_volume + put_trades
    if call_activity <= 0 and put_activity <= 0:
        return None
    total = call_activity + put_activity
    call_share = call_activity / total if total else 0.0
    if call_share >= 0.65:
        return "call_activity_elevated"
    if call_share <= 0.35:
        return "put_activity_elevated"
    return "balanced_activity"


def _target_state_features(
    index: int,
    closes: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    volumes: Sequence[float | None],
    vwaps: Sequence[float | None],
    spreads: Sequence[float | None],
    dollar_volumes: Sequence[float | None],
    feature_cache: _TargetRollingFeatures | None = None,
    option_chain_state: Mapping[str, Any] | None = None,
    include_option_chain_state: bool = True,
) -> dict[str, Any]:
    close = closes[index]
    returns_cache: dict[tuple[int, int, int], list[float]] = {}
    state: dict[str, Any] = {
        "state_observation_windows": list(STATE_WINDOW_LABELS),
        "state_window_sync_policy": STATE_WINDOW_SYNC_POLICY,
        "target_price_state": {},
        "target_direction_return_shape": {},
        "target_trend_quality_state": {},
        "target_trend_age_state": {},
        "target_exhaustion_decay_state": {},
        "target_volatility_range_state": {},
        "target_gap_jump_state": {},
        "target_volume_activity_state": {},
        "target_liquidity_tradability_state": {},
        "target_vwap_location_state": {},
        "target_session_position_state": {},
        "target_peer_rank_state": {},
        "target_shortability_state": {},
        "target_event_risk_state": {},
        "target_data_quality_state": {},
    }
    if include_option_chain_state:
        state["target_option_chain_state"] = {}
    state["target_price_state"]["bar_close"] = close
    state["target_price_state"]["bar_high"] = highs[index]
    state["target_price_state"]["bar_low"] = lows[index]
    session_start = max(0, index - 389)
    state["target_price_state"]["session_open"] = feature_cache.session_open[index] if feature_cache else next((value for value in closes[session_start : index + 1] if value is not None), None)
    for label, window in STATE_WINDOW_MINUTES.items():
        window_return = feature_cache.window_return(index, window) if feature_cache else _window_return(closes, index, window)
        realized_vol = feature_cache.realized_vol(index, window) if feature_cache else _realized_vol(closes, index, window, returns_cache)
        state["target_direction_return_shape"][f"return_{label}"] = window_return
        state["target_volatility_range_state"][f"realized_vol_{label}"] = realized_vol
        state["target_volatility_range_state"][f"range_position_{label}"] = feature_cache.range_position(index, window) if feature_cache else _range_position(closes, highs, lows, index, window)
        state["target_volatility_range_state"][f"atr_pct_{label}"] = feature_cache.atr_pct(index, window) if feature_cache else _atr_pct(closes, highs, lows, index, window)
        state["target_volume_activity_state"][f"relative_volume_{label}"] = feature_cache.relative_to_window("volume", index, window) if feature_cache else _relative_to_window(volumes, index, window)
        state["target_volume_activity_state"][f"relative_dollar_volume_{label}"] = feature_cache.relative_to_window("dollar_volume", index, window) if feature_cache else _relative_to_window(dollar_volumes, index, window)
        state["target_trend_quality_state"][f"trend_quality_{label}"] = _trend_quality_score_from_cache(feature_cache, closes, index, window, returns_cache)
        state["target_trend_quality_state"][f"path_stability_{label}"] = feature_cache.path_stability_score(index, window) if feature_cache else _path_stability_score(closes, index, window, returns_cache)
        state["target_trend_age_state"][f"trend_age_bars_{label}"] = feature_cache.trend_age_bars(index, window) if feature_cache else _trend_age_bars(closes, index, window, returns_cache)
        state["target_trend_age_state"][f"direction_flip_count_{label}"] = feature_cache.direction_flip_count(index, window) if feature_cache else _direction_flip_count(closes, index, window, returns_cache)
        state["target_trend_age_state"][f"state_persistence_score_{label}"] = feature_cache.state_persistence_score(index, window) if feature_cache else _state_persistence_score(closes, index, window, returns_cache)
        state["target_exhaustion_decay_state"][f"momentum_decay_score_{label}"] = feature_cache.momentum_decay_score(index, window) if feature_cache else _momentum_decay_score(closes, index, window, returns_cache)
        state["target_exhaustion_decay_state"][f"volume_exhaustion_score_{label}"] = feature_cache.volume_exhaustion_score(index, window) if feature_cache else _volume_exhaustion_score(volumes, index, window)
        state["target_exhaustion_decay_state"][f"volatility_exhaustion_score_{label}"] = feature_cache.volatility_exhaustion_score(index, window) if feature_cache else _volatility_exhaustion_score(closes, index, window, returns_cache)
        state["target_exhaustion_decay_state"][f"late_trend_risk_score_{label}"] = feature_cache.late_trend_risk_score(index, window) if feature_cache else _late_trend_risk_score(closes, volumes, index, window, returns_cache)

    state["multi_frame_state"] = _target_multi_frame_state(state)
    state["target_trend_age_state"]["time_since_last_direction_flip_bars"] = feature_cache.time_since_last_direction_flip(index) if feature_cache else _time_since_last_direction_flip(closes, index, returns_cache)
    state["target_trend_quality_state"]["return_10min_minus_1h"] = _delta(
        state["target_direction_return_shape"].get("return_10min"),
        state["target_direction_return_shape"].get("return_1h"),
    )
    state["target_trend_quality_state"]["return_1h_minus_1D"] = _delta(
        state["target_direction_return_shape"].get("return_1h"),
        state["target_direction_return_shape"].get("return_1D"),
    )
    state["target_gap_jump_state"]["current_bar_return"] = _window_return(closes, index, 1)
    state["target_gap_jump_state"]["current_range_pct"] = None if close in (None, 0) or highs[index] is None or lows[index] is None else (highs[index] - lows[index]) / close
    state["target_liquidity_tradability_state"]["spread_bps"] = spreads[index]
    state["target_liquidity_tradability_state"]["dollar_volume"] = dollar_volumes[index]
    state["target_vwap_location_state"]["vwap_distance_pct"] = _safe_ratio_delta(close, vwaps[index])
    state["target_session_position_state"].update(_session_position_state(index, closes, highs, lows, vwaps, feature_cache=feature_cache))
    state["target_shortability_state"].update({"shortable_state": None, "borrow_availability_score": None, "borrow_cost_score": None, "hard_to_borrow_flag": None, "locate_quality_score": None, "short_sale_constraint_score": None, "data_policy": "optional_overlay_not_required_for_state_vector"})
    if include_option_chain_state:
        state["target_option_chain_state"].update(option_chain_state or {"data_policy": "optional_overlay_not_available"})
    state["target_event_risk_state"].update({"earnings_proximity_score": None, "scheduled_event_risk_score": None, "news_shock_state": None, "halt_risk_score": None, "macro_event_window_flag": None, "data_policy": "optional_overlay_not_required_for_state_vector"})
    state["target_data_quality_state"]["has_close"] = close is not None
    state["target_data_quality_state"]["has_high_low"] = highs[index] is not None and lows[index] is not None
    state["target_data_quality_state"]["has_volume"] = volumes[index] is not None
    state["target_data_quality_state"]["history_bars"] = index + 1
    return state


def _target_multi_frame_state(target_state: Mapping[str, Any]) -> dict[str, dict[str, float | int | None]]:
    direction = target_state.get("target_direction_return_shape") if isinstance(target_state.get("target_direction_return_shape"), Mapping) else {}
    volatility = target_state.get("target_volatility_range_state") if isinstance(target_state.get("target_volatility_range_state"), Mapping) else {}
    trend = target_state.get("target_trend_quality_state") if isinstance(target_state.get("target_trend_quality_state"), Mapping) else {}
    trend_age = target_state.get("target_trend_age_state") if isinstance(target_state.get("target_trend_age_state"), Mapping) else {}
    exhaustion = target_state.get("target_exhaustion_decay_state") if isinstance(target_state.get("target_exhaustion_decay_state"), Mapping) else {}
    volume = target_state.get("target_volume_activity_state") if isinstance(target_state.get("target_volume_activity_state"), Mapping) else {}
    frames: dict[str, dict[str, float | int | None]] = {}
    for label, window in STATE_WINDOW_MINUTES.items():
        frames[label] = {
            "return": _safe_float(direction.get(f"return_{label}")),
            "realized_vol": _safe_float(volatility.get(f"realized_vol_{label}")),
            "atr_pct": _safe_float(volatility.get(f"atr_pct_{label}")),
            "range_position": _safe_float(volatility.get(f"range_position_{label}")),
            "relative_volume": _safe_float(volume.get(f"relative_volume_{label}")),
            "relative_dollar_volume": _safe_float(volume.get(f"relative_dollar_volume_{label}")),
            "trend_quality": _safe_float(trend.get(f"trend_quality_{label}")),
            "path_stability": _safe_float(trend.get(f"path_stability_{label}")),
            "trend_age_bars": _safe_float(trend_age.get(f"trend_age_bars_{label}")),
            "direction_flip_count": _safe_float(trend_age.get(f"direction_flip_count_{label}")),
            "state_persistence_score": _safe_float(trend_age.get(f"state_persistence_score_{label}")),
            "late_trend_risk_score": _safe_float(exhaustion.get(f"late_trend_risk_score_{label}")),
            "observation_minutes": float(window),
        }
    return frames


def _cross_state_features(target_state: Mapping[str, Any], market_state: Mapping[str, Any], sector_state: Mapping[str, Any]) -> dict[str, Any]:
    market_payload = market_state.get("market_context_payload") if isinstance(market_state.get("market_context_payload"), Mapping) else {}
    sector_payload = sector_state.get("sector_context_payload") if isinstance(sector_state.get("sector_context_payload"), Mapping) else {}
    beta_sector_market = _first_float(sector_payload, "beta_sector_market", "sector_market_beta", "2_conditional_beta_score")
    beta_target_market = _first_float(sector_payload, "beta_target_market", "target_market_beta")
    beta_target_sector = _first_float(sector_payload, "beta_target_sector", "target_sector_beta")
    multi_frame = _cross_multi_frame_state(
        target_state=target_state,
        market_payload=market_payload,
        sector_payload=sector_payload,
        beta_sector_market=beta_sector_market,
        beta_target_market=beta_target_market,
        beta_target_sector=beta_target_sector,
    )
    frame_primary = multi_frame.get("1h", {})
    return {
        "state_observation_windows": list(STATE_WINDOW_LABELS),
        "state_window_sync_policy": STATE_WINDOW_SYNC_POLICY,
        "multi_frame_state": multi_frame,
        "target_vs_market_residual_direction": frame_primary.get("target_vs_market_residual_direction"),
        "target_vs_sector_residual_direction": frame_primary.get("target_vs_sector_residual_direction"),
        "target_vs_market_volatility": frame_primary.get("target_vs_market_volatility"),
        "target_vs_sector_volatility": frame_primary.get("target_vs_sector_volatility"),
        "target_market_beta_correlation": beta_target_market,
        "target_sector_beta_correlation": beta_target_sector,
        "sector_confirmation_state": frame_primary.get("sector_confirmation_state"),
        "idiosyncratic_residual_state": frame_primary.get("idiosyncratic_residual_state"),
        "relative_liquidity_tradability_state": None,
        "beta_adjustment_policy": "uses_beta_adjusted_target_minus_market_and_sector_residuals_when_point_in_time_betas_are_available_else_simple_residuals",
    }


def _cross_multi_frame_state(
    *,
    target_state: Mapping[str, Any],
    market_payload: Mapping[str, Any],
    sector_payload: Mapping[str, Any],
    beta_sector_market: float | None,
    beta_target_market: float | None,
    beta_target_sector: float | None,
) -> dict[str, dict[str, float | str | None]]:
    frames: dict[str, dict[str, float | str | None]] = {}
    for label in STATE_WINDOW_LABELS:
        target_return = _nested_float(target_state, "target_direction_return_shape", f"return_{label}")
        target_vol = _nested_float(target_state, "target_volatility_range_state", f"realized_vol_{label}")
        market_return = _first_float(market_payload, f"market_return_{label}", "market_return", f"return_{label}", "relative_strength_return")
        sector_return = _first_float(sector_payload, f"sector_return_{label}", "sector_return", f"return_{label}", "relative_strength_return")
        market_vol = _first_float(market_payload, f"market_volatility_{label}", "market_volatility", f"realized_vol_{label}")
        sector_vol = _first_float(sector_payload, f"sector_volatility_{label}", "sector_volatility", f"realized_vol_{label}", "relative_strength_realized_vol_20d_ratio")
        simple_market_residual = _delta(target_return, market_return)
        simple_sector_residual = _delta(target_return, sector_return)
        sector_beta_residual = _beta_residual(sector_return, ((market_return, beta_sector_market),))
        target_beta_residual = _beta_residual(target_return, ((market_return, beta_target_market), (sector_beta_residual, beta_target_sector)))
        sector_residual = target_beta_residual if target_beta_residual is not None else simple_sector_residual
        frames[label] = {
            "target_return": target_return,
            "market_return": market_return,
            "sector_return": sector_return,
            "target_vs_market_residual_direction": simple_market_residual,
            "target_vs_sector_residual_direction": sector_residual,
            "target_vs_market_volatility": _safe_div(target_vol, market_vol),
            "target_vs_sector_volatility": _safe_div(target_vol, sector_vol),
            "sector_confirmation_state": _sector_confirmation(target_return, sector_return),
            "idiosyncratic_residual_state": sector_residual if sector_residual is not None else _delta(simple_market_residual, sector_return),
        }
    return frames


def _feature_quality(
    index: int,
    bar: Bar,
    market_context: ContextRow | None,
    sector_context: ContextRow | None,
    option_diagnostics: Mapping[str, Any] | None = None,
    include_option_chain_diagnostics: bool = True,
) -> dict[str, Any]:
    diagnostics = {
        "history_bars": index + 1,
        "has_market_context": market_context is not None,
        "has_sector_context": sector_context is not None,
        "has_target_close": bar.close is not None,
        "has_target_volume": bar.volume is not None,
        "has_spread_bps": bar.spread_bps is not None,
    }
    if include_option_chain_diagnostics:
        diagnostics["target_option_chain_diagnostics"] = dict(option_diagnostics or {"has_option_chain_source": False})
    return diagnostics


def _attach_peer_ranks(rows: list[dict[str, Any]]) -> None:
    by_time: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_time.setdefault(str(row.get("available_time")), []).append(row)
    rank_specs = {
        "trend_quality_rank_in_peer_pool_1h": lambda r: _nested_float(r["target_state_features"], "target_trend_quality_state", "trend_quality_1h"),
        "path_stability_rank_in_peer_pool_1h": lambda r: _nested_float(r["target_state_features"], "target_trend_quality_state", "path_stability_1h"),
        "noise_low_rank_in_peer_pool_1h": lambda r: _invert_for_rank(_nested_float(r["target_state_features"], "target_trend_quality_state", "path_stability_1h")),
        "liquidity_tradability_rank_in_peer_pool": lambda r: _liquidity_rank_value(r["target_state_features"]),
        "residual_direction_strength_rank_in_peer_pool_1h": lambda r: abs(_safe_float(r["cross_state_features"].get("idiosyncratic_residual_state")) or 0.0),
        "transition_risk_low_rank_in_peer_pool_1h": lambda r: _invert_for_rank(_nested_float(r["target_state_features"], "target_exhaustion_decay_state", "late_trend_risk_score_1h")),
    }
    for peers in by_time.values():
        for field, getter in rank_specs.items():
            values = [(row, getter(row)) for row in peers]
            ranked = sorted([item for item in values if item[1] is not None], key=lambda item: item[1], reverse=True)
            ranks = {id(row): rank for rank, (row, _value) in enumerate(ranked, start=1)}
            for row in peers:
                target_state = row.get("target_state_features")
                if isinstance(target_state, dict):
                    target_state.setdefault("target_peer_rank_state", {})[field] = ranks.get(id(row))


def _liquidity_rank_value(target_state: Mapping[str, Any]) -> float | None:
    liquidity = target_state.get("target_liquidity_tradability_state")
    if not isinstance(liquidity, Mapping):
        return None
    spread = _safe_float(liquidity.get("spread_bps"))
    dollar_volume = _safe_float(liquidity.get("dollar_volume"))
    spread_score = None if spread is None else max(0.0, 1.0 - min(spread / 100.0, 1.0))
    volume_score = None if dollar_volume is None else min(math.log10(max(dollar_volume, 1.0)) / 8.0, 1.0)
    return _average([spread_score, volume_score])


def _invert_for_rank(value: float | None) -> float | None:
    return None if value is None else 1.0 - max(0.0, min(value, 1.0))


def _session_position_state(
    index: int,
    closes: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    vwaps: Sequence[float | None],
    feature_cache: _TargetRollingFeatures | None = None,
) -> dict[str, Any]:
    minute_of_session = index
    close = closes[index]
    session_window = min(index + 1, 390)
    session_start = max(0, index - session_window + 1)
    if feature_cache:
        session_open = feature_cache.session_open[index]
        session_high = feature_cache.session_high[index]
        session_low = feature_cache.session_low[index]
    else:
        session_open = next((value for value in closes[session_start : index + 1] if value is not None), None)
        high_values = _window_values(highs, index, session_window)
        low_values = _window_values(lows, index, session_window)
        session_high = max(high_values) if high_values else None
        session_low = min(low_values) if low_values else None
    range_position = None if close is None or session_high is None or session_low is None or session_high == session_low else (close - session_low) / (session_high - session_low)
    return {
        "window_policy": "completed_1min_bars",
        "minutes_since_open": minute_of_session,
        "minutes_to_close": max(390 - minute_of_session, 0),
        "session_phase": "opening_range" if minute_of_session < 30 else "midday" if minute_of_session < 330 else "closing_window",
        "is_opening_range": minute_of_session < 30,
        "is_midday": 30 <= minute_of_session < 330,
        "is_closing_window": minute_of_session >= 330,
        "distance_to_open": _safe_ratio_delta(close, session_open),
        "distance_to_prev_close": None,
        "distance_to_vwap": _safe_ratio_delta(close, vwaps[index]),
        "is_near_daily_high_low": None if range_position is None else range_position >= 0.9 or range_position <= 0.1,
        "session_range_position": range_position,
    }


def _window_values(values: Sequence[float | None], index: int, window: int) -> list[float]:
    start = max(0, index - window + 1)
    return [float(value) for value in values[start : index + 1] if value is not None]


def _window_return(values: Sequence[float | None], index: int, window: int) -> float | None:
    if index < window:
        return None
    current = values[index]
    previous = values[index - window]
    if current is None or previous in (None, 0):
        return None
    return current / previous - 1


def _realized_vol(values: Sequence[float | None], index: int, window: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> float | None:
    if index < 1:
        return None
    returns = _incremental_returns(values, index, window, returns_cache, log_returns=True)
    return _pstdev(returns) if len(returns) >= 2 else None


def _range_position(closes: Sequence[float | None], highs: Sequence[float | None], lows: Sequence[float | None], index: int, window: int) -> float | None:
    close = closes[index]
    if close is None:
        return None
    high_values = _window_values(highs, index, window)
    low_values = _window_values(lows, index, window)
    if not high_values or not low_values:
        return None
    high = max(high_values)
    low = min(low_values)
    return None if high == low else (close - low) / (high - low)


def _trend_quality_score_from_cache(
    feature_cache: _TargetRollingFeatures | None,
    values: Sequence[float | None],
    index: int,
    window: int,
    returns_cache: dict[tuple[int, int, int], list[float]] | None = None,
) -> float | None:
    if feature_cache is None:
        return _trend_quality_score(values, index, window, returns_cache)
    ret = feature_cache.window_return(index, window)
    stability = feature_cache.path_stability_score(index, window)
    if ret is None and stability is None:
        return None
    direction_strength = None if ret is None else min(abs(math.tanh(ret / 0.03)), 1.0)
    return _average([direction_strength, stability])


def _atr_pct(closes: Sequence[float | None], highs: Sequence[float | None], lows: Sequence[float | None], index: int, window: int) -> float | None:
    close = closes[index]
    if close in (None, 0) or index < 1:
        return None
    true_ranges: list[float] = []
    start = max(1, index - window + 1)
    for pos in range(start, index + 1):
        high = highs[pos]
        low = lows[pos]
        previous_close = closes[pos - 1]
        if high is None or low is None:
            continue
        candidates = [high - low]
        if previous_close is not None:
            candidates.extend([abs(high - previous_close), abs(low - previous_close)])
        true_ranges.append(max(candidates))
    return None if not true_ranges else _mean(true_ranges) / close


def _relative_to_window(values: Sequence[float | None], index: int, window: int) -> float | None:
    current = values[index]
    history = _window_values(values, index, window)
    if current is None or not history:
        return None
    avg = _mean(history)
    return None if avg == 0 else current / avg


def _trend_quality_score(values: Sequence[float | None], index: int, window: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> float | None:
    ret = _window_return(values, index, window)
    stability = _path_stability_score(values, index, window, returns_cache)
    if ret is None and stability is None:
        return None
    direction_strength = None if ret is None else min(abs(math.tanh(ret / 0.03)), 1.0)
    return _average([direction_strength, stability])


def _path_stability_score(values: Sequence[float | None], index: int, window: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> float | None:
    returns = _incremental_returns(values, index, window, returns_cache)
    if len(returns) < 2:
        return None
    total_abs = sum(abs(value) for value in returns)
    net_abs = abs(sum(returns))
    efficiency = None if total_abs == 0 else net_abs / total_abs
    flips = _direction_flip_count(values, index, window, returns_cache)
    flip_penalty = None if flips is None else 1.0 - min(flips / max(len(returns) - 1, 1), 1.0)
    vol = _pstdev(returns) if len(returns) >= 2 else None
    vol_stability = None if vol is None else 1.0 - min(vol / 0.02, 1.0)
    return _average([efficiency, flip_penalty, vol_stability])


def _incremental_returns(
    values: Sequence[float | None],
    index: int,
    window: int,
    cache: dict[tuple[int, int, int], list[float]] | None = None,
    *,
    log_returns: bool = False,
) -> list[float]:
    key = (id(values), index, window * (-1 if log_returns else 1))
    if cache is not None and key in cache:
        return cache[key]
    returns: list[float] = []
    start = max(1, index - window + 1)
    for pos in range(start, index + 1):
        current = values[pos]
        previous = values[pos - 1]
        if current is not None and previous not in (None, 0):
            returns.append(math.log(current / previous) if log_returns else current / previous - 1.0)
    if cache is not None:
        cache[key] = returns
    return returns


def _direction_flip_count(values: Sequence[float | None], index: int, window: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> int | None:
    returns = [value for value in _incremental_returns(values, index, window, returns_cache) if value != 0]
    if len(returns) < 2:
        return None
    signs = [1 if value > 0 else -1 for value in returns]
    return sum(1 for left, right in zip(signs, signs[1:]) if left != right)


def _time_since_last_direction_flip(values: Sequence[float | None], index: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> int | None:
    returns = _incremental_returns(values, index, min(index + 1, STATE_WINDOW_MINUTES["1W"]), returns_cache)
    if len(returns) < 2:
        return None
    signs = [1 if value > 0 else -1 if value < 0 else 0 for value in returns]
    for offset in range(len(signs) - 1, 0, -1):
        if signs[offset] and signs[offset - 1] and signs[offset] != signs[offset - 1]:
            return len(signs) - offset
    return len(signs)


def _trend_age_bars(values: Sequence[float | None], index: int, window: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> int | None:
    returns = _incremental_returns(values, index, window, returns_cache)
    if not returns:
        return None
    last_sign = 1 if returns[-1] > 0 else -1 if returns[-1] < 0 else 0
    if last_sign == 0:
        return 0
    age = 0
    for value in reversed(returns):
        sign = 1 if value > 0 else -1 if value < 0 else 0
        if sign != last_sign:
            break
        age += 1
    return age


def _state_persistence_score(values: Sequence[float | None], index: int, window: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> float | None:
    age = _trend_age_bars(values, index, window, returns_cache)
    if age is None:
        return None
    return min(age / max(window, 1), 1.0)


def _momentum_decay_score(values: Sequence[float | None], index: int, window: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> float | None:
    returns = _incremental_returns(values, index, window, returns_cache)
    if len(returns) < 4:
        return None
    midpoint = len(returns) // 2
    first = _mean(abs(value) for value in returns[:midpoint])
    second = _mean(abs(value) for value in returns[midpoint:])
    return None if first == 0 else max(0.0, min((first - second) / first, 1.0))


def _volume_exhaustion_score(volumes: Sequence[float | None], index: int, window: int) -> float | None:
    history = _window_values(volumes, index, window)
    current = volumes[index]
    if current is None or len(history) < 4:
        return None
    midpoint = len(history) // 2
    first = _mean(history[:midpoint])
    second = _mean(history[midpoint:])
    return None if first == 0 else max(0.0, min((first - second) / first, 1.0))


def _volatility_exhaustion_score(values: Sequence[float | None], index: int, window: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> float | None:
    returns = _incremental_returns(values, index, window, returns_cache)
    if len(returns) < 4:
        return None
    midpoint = len(returns) // 2
    first = _pstdev(returns[:midpoint]) if len(returns[:midpoint]) >= 2 else None
    second = _pstdev(returns[midpoint:]) if len(returns[midpoint:]) >= 2 else None
    if first in (None, 0) or second is None:
        return None
    return max(0.0, min((second - first) / first, 1.0))


def _late_trend_risk_score(values: Sequence[float | None], volumes: Sequence[float | None], index: int, window: int, returns_cache: dict[tuple[int, int, int], list[float]] | None = None) -> float | None:
    return _average([
        _state_persistence_score(values, index, window, returns_cache),
        _momentum_decay_score(values, index, window, returns_cache),
        _volume_exhaustion_score(volumes, index, window),
        _volatility_exhaustion_score(values, index, window, returns_cache),
    ])


def _beta_residual(base: float | None, adjustments: Sequence[tuple[float | None, float | None]]) -> float | None:
    if base is None:
        return None
    residual = base
    used = False
    for value, beta in adjustments:
        if value is None or beta is None:
            continue
        residual -= beta * value
        used = True
    return residual if used else None


def _sector_confirmation(target_return: float | None, sector_return: float | None) -> str | None:
    if target_return is None or sector_return is None:
        return None
    if target_return == 0 or sector_return == 0:
        return "flat_or_mixed"
    return "sector_confirmed" if (target_return > 0) == (sector_return > 0) else "sector_divergent"


def _nested_float(payload: Mapping[str, Any], group: str, key: str) -> float | None:
    value = payload.get(group)
    if not isinstance(value, Mapping):
        return None
    return _safe_float(value.get(key))


def _first_float(payload: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _safe_float(payload.get(key))
        if value is not None:
            return value
    return None


def _delta(left: Any, right: Any) -> float | None:
    left_float = _safe_float(left)
    right_float = _safe_float(right)
    return None if left_float is None or right_float is None else left_float - right_float


def _safe_ratio_delta(value: Any, anchor: Any) -> float | None:
    value_float = _safe_float(value)
    anchor_float = _safe_float(anchor)
    if value_float is None or anchor_float in (None, 0):
        return None
    return value_float / anchor_float - 1


def _safe_div(numerator: Any, denominator: Any) -> float | None:
    numerator_float = _safe_float(numerator)
    denominator_float = _safe_float(denominator)
    if numerator_float is None or denominator_float in (None, 0):
        return None
    return numerator_float / denominator_float


def _average(values: Iterable[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return _mean(clean) if clean else None


def _mean(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += float(value)
        count += 1
    return total / count


def _pstdev(values: Sequence[float]) -> float:
    avg = _mean(values)
    return math.sqrt(sum((float(value) - avg) ** 2 for value in values) / len(values))


def _pstdev_from_sums(total: float, sumsq: float, count: int) -> float | None:
    if count < 2:
        return None
    variance = max((sumsq / count) - ((total / count) ** 2), 0.0)
    return math.sqrt(variance)


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif value is None or str(value).strip() == "":
        raise TargetStateVectorError("timestamp/available_time is required")
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET)
