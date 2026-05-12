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
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, pstdev
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
FEATURE = "feature_03_target_state_vector"
DEFAULT_VECTOR_VERSION = "target_context_state"
DEFAULT_RUN_ID = "adhoc"
STATE_WINDOWS = (5, 15, 60, 390)
STATE_WINDOW_LABELS = tuple(f"{window}min" for window in STATE_WINDOWS)
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
class TargetStateInputs:
    bars_by_candidate: dict[str, list[Bar]]
    market_context_rows: tuple[ContextRow, ...] = ()
    sector_context_rows: tuple[ContextRow, ...] = ()


class TargetStateVectorError(ValueError):
    """Raised when target state-vector inputs are invalid."""


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
) -> TargetStateInputs:
    candidates = _candidate_map(candidate_rows)
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
    )


def generate_rows(
    inputs: TargetStateInputs,
    *,
    run_id: str = DEFAULT_RUN_ID,
    target_context_state_version: str = DEFAULT_VECTOR_VERSION,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target_candidate_id in sorted(inputs.bars_by_candidate):
        rows.extend(
            generate_candidate_rows(
                inputs.bars_by_candidate[target_candidate_id],
                inputs.market_context_rows,
                inputs.sector_context_rows,
                run_id=run_id,
                target_context_state_version=target_context_state_version,
            )
        )
    _attach_peer_ranks(rows)
    return rows


def generate_candidate_rows(
    bars: Sequence[Bar],
    market_context_rows: Sequence[ContextRow] = (),
    sector_context_rows: Sequence[ContextRow] = (),
    *,
    run_id: str = DEFAULT_RUN_ID,
    target_context_state_version: str = DEFAULT_VECTOR_VERSION,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    closes = [bar.close for bar in bars]
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    volumes = [bar.volume for bar in bars]
    vwaps = [bar.bar_vwap for bar in bars]
    spreads = [bar.spread_bps for bar in bars]
    dollar_volumes = [bar.dollar_volume for bar in bars]

    for index, bar in enumerate(bars):
        market_context = _latest_context(market_context_rows, bar.available_time)
        sector_context = _latest_context(sector_context_rows, bar.available_time)
        target_state = _target_state_features(index, closes, highs, lows, volumes, vwaps, spreads, dollar_volumes)
        market_state = _market_state_features(market_context)
        sector_state = _sector_state_features(sector_context)
        cross_state = _cross_state_features(target_state, market_state, sector_state)
        rows.append(
            {
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
                "feature_quality_diagnostics": _feature_quality(index, bar, market_context, sector_context),
            }
        )
    return rows


def payload_columns(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted({key for row in rows for key in row if key not in METADATA_COLUMNS})


def _candidate_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    candidates: dict[str, str] = {}
    for row in rows:
        target_candidate_id = str(row.get("target_candidate_id") or "").strip()
        symbol = str(row.get("symbol") or row.get("routing_symbol_ref") or row.get("audit_symbol_ref") or "").strip().upper()
        if target_candidate_id and symbol:
            candidates[symbol] = target_candidate_id
    return candidates


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
    }
    if context is None:
        projected.update({group: None for group in groups})
        projected[default_key] = {}
        return projected
    payload = dict(context.payload)
    projected.update({group: payload.get(group) for group in groups})
    projected[default_key] = {key: value for key, value in payload.items() if key not in groups}
    return projected


def _target_state_features(
    index: int,
    closes: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    volumes: Sequence[float | None],
    vwaps: Sequence[float | None],
    spreads: Sequence[float | None],
    dollar_volumes: Sequence[float | None],
) -> dict[str, Any]:
    close = closes[index]
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
    state["target_price_state"]["bar_close"] = close
    state["target_price_state"]["bar_high"] = highs[index]
    state["target_price_state"]["bar_low"] = lows[index]
    state["target_price_state"]["session_open"] = next((value for value in closes[: index + 1] if value is not None), None)
    for window in STATE_WINDOWS:
        window_return = _window_return(closes, index, window)
        realized_vol = _realized_vol(closes, index, window)
        state["target_direction_return_shape"][f"return_{window}min"] = window_return
        state["target_volatility_range_state"][f"realized_vol_{window}min"] = realized_vol
        state["target_volatility_range_state"][f"range_position_{window}min"] = _range_position(closes, highs, lows, index, window)
        state["target_volatility_range_state"][f"atr_pct_{window}min"] = _atr_pct(closes, highs, lows, index, window)
        state["target_volume_activity_state"][f"relative_volume_{window}min"] = _relative_to_window(volumes, index, window)
        state["target_volume_activity_state"][f"relative_dollar_volume_{window}min"] = _relative_to_window(dollar_volumes, index, window)
        state["target_trend_quality_state"][f"trend_quality_{window}min"] = _trend_quality_score(closes, index, window)
        state["target_trend_quality_state"][f"path_stability_{window}min"] = _path_stability_score(closes, index, window)
        state["target_trend_age_state"][f"trend_age_bars_{window}min"] = _trend_age_bars(closes, index, window)
        state["target_trend_age_state"][f"direction_flip_count_{window}min"] = _direction_flip_count(closes, index, window)
        state["target_trend_age_state"][f"state_persistence_score_{window}min"] = _state_persistence_score(closes, index, window)
        state["target_exhaustion_decay_state"][f"momentum_decay_score_{window}min"] = _momentum_decay_score(closes, index, window)
        state["target_exhaustion_decay_state"][f"volume_exhaustion_score_{window}min"] = _volume_exhaustion_score(volumes, index, window)
        state["target_exhaustion_decay_state"][f"volatility_exhaustion_score_{window}min"] = _volatility_exhaustion_score(closes, index, window)
        state["target_exhaustion_decay_state"][f"late_trend_risk_score_{window}min"] = _late_trend_risk_score(closes, volumes, index, window)

    state["target_trend_age_state"]["time_since_last_direction_flip_bars"] = _time_since_last_direction_flip(closes, index)
    state["target_trend_quality_state"]["return_5m_minus_15m"] = _delta(
        state["target_direction_return_shape"].get("return_5min"),
        state["target_direction_return_shape"].get("return_15min"),
    )
    state["target_trend_quality_state"]["return_15m_minus_60m"] = _delta(
        state["target_direction_return_shape"].get("return_15min"),
        state["target_direction_return_shape"].get("return_60min"),
    )
    state["target_gap_jump_state"]["current_bar_return"] = _window_return(closes, index, 1)
    state["target_gap_jump_state"]["current_range_pct"] = None if close in (None, 0) or highs[index] is None or lows[index] is None else (highs[index] - lows[index]) / close
    state["target_liquidity_tradability_state"]["spread_bps"] = spreads[index]
    state["target_liquidity_tradability_state"]["dollar_volume"] = dollar_volumes[index]
    state["target_vwap_location_state"]["vwap_distance_pct"] = _safe_ratio_delta(close, vwaps[index])
    state["target_session_position_state"].update(_session_position_state(index, closes, highs, lows, vwaps))
    state["target_shortability_state"].update({"shortable_state": None, "borrow_availability_score": None, "borrow_cost_score": None, "hard_to_borrow_flag": None, "locate_quality_score": None, "short_sale_constraint_score": None, "data_policy": "optional_overlay_not_required_for_state_vector"})
    state["target_event_risk_state"].update({"earnings_proximity_score": None, "scheduled_event_risk_score": None, "news_shock_state": None, "halt_risk_score": None, "macro_event_window_flag": None, "data_policy": "optional_overlay_not_required_for_state_vector"})
    state["target_data_quality_state"]["has_close"] = close is not None
    state["target_data_quality_state"]["has_high_low"] = highs[index] is not None and lows[index] is not None
    state["target_data_quality_state"]["has_volume"] = volumes[index] is not None
    state["target_data_quality_state"]["history_bars"] = index + 1
    return state


def _cross_state_features(target_state: Mapping[str, Any], market_state: Mapping[str, Any], sector_state: Mapping[str, Any]) -> dict[str, Any]:
    target_return = _nested_float(target_state, "target_direction_return_shape", "return_15min")
    target_vol = _nested_float(target_state, "target_volatility_range_state", "realized_vol_15min")
    market_payload = market_state.get("market_context_payload") if isinstance(market_state.get("market_context_payload"), Mapping) else {}
    sector_payload = sector_state.get("sector_context_payload") if isinstance(sector_state.get("sector_context_payload"), Mapping) else {}
    market_return = _first_float(market_payload, "market_return_15min", "market_return", "return_15min", "relative_strength_return")
    sector_return = _first_float(sector_payload, "sector_return_15min", "sector_return", "return_15min", "relative_strength_return")
    market_vol = _first_float(market_payload, "market_volatility_15min", "market_volatility", "realized_vol_15min")
    sector_vol = _first_float(sector_payload, "sector_volatility_15min", "sector_volatility", "realized_vol_15min", "relative_strength_realized_vol_20d_ratio")
    beta_sector_market = _first_float(sector_payload, "beta_sector_market", "sector_market_beta", "2_conditional_beta_score")
    beta_target_market = _first_float(sector_payload, "beta_target_market", "target_market_beta")
    beta_target_sector = _first_float(sector_payload, "beta_target_sector", "target_sector_beta")
    simple_market_residual = _delta(target_return, market_return)
    simple_sector_residual = _delta(target_return, sector_return)
    sector_beta_residual = _beta_residual(sector_return, ((market_return, beta_sector_market),))
    target_beta_residual = _beta_residual(target_return, ((market_return, beta_target_market), (sector_beta_residual, beta_target_sector)))
    return {
        "state_observation_windows": list(STATE_WINDOW_LABELS),
        "state_window_sync_policy": STATE_WINDOW_SYNC_POLICY,
        "target_vs_market_residual_direction": simple_market_residual,
        "target_vs_sector_residual_direction": target_beta_residual if target_beta_residual is not None else simple_sector_residual,
        "target_vs_market_volatility": _safe_div(target_vol, market_vol),
        "target_vs_sector_volatility": _safe_div(target_vol, sector_vol),
        "target_market_beta_correlation": beta_target_market,
        "target_sector_beta_correlation": beta_target_sector,
        "sector_confirmation_state": _sector_confirmation(target_return, sector_return),
        "idiosyncratic_residual_state": target_beta_residual if target_beta_residual is not None else _delta(simple_market_residual, sector_return),
        "relative_liquidity_tradability_state": None,
        "beta_adjustment_policy": "uses_beta_adjusted_target_minus_market_and_sector_residuals_when_point_in_time_betas_are_available_else_simple_residuals",
    }


def _feature_quality(index: int, bar: Bar, market_context: ContextRow | None, sector_context: ContextRow | None) -> dict[str, Any]:
    return {
        "history_bars": index + 1,
        "has_market_context": market_context is not None,
        "has_sector_context": sector_context is not None,
        "has_target_close": bar.close is not None,
        "has_target_volume": bar.volume is not None,
        "has_spread_bps": bar.spread_bps is not None,
    }


def _attach_peer_ranks(rows: list[dict[str, Any]]) -> None:
    by_time: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_time.setdefault(str(row.get("available_time")), []).append(row)
    rank_specs = {
        "trend_quality_rank_in_peer_pool_15min": lambda r: _nested_float(r["target_state_features"], "target_trend_quality_state", "trend_quality_15min"),
        "path_stability_rank_in_peer_pool_15min": lambda r: _nested_float(r["target_state_features"], "target_trend_quality_state", "path_stability_15min"),
        "noise_low_rank_in_peer_pool_15min": lambda r: _invert_for_rank(_nested_float(r["target_state_features"], "target_trend_quality_state", "path_stability_15min")),
        "liquidity_tradability_rank_in_peer_pool": lambda r: _liquidity_rank_value(r["target_state_features"]),
        "residual_direction_strength_rank_in_peer_pool_15min": lambda r: abs(_safe_float(r["cross_state_features"].get("idiosyncratic_residual_state")) or 0.0),
        "transition_risk_low_rank_in_peer_pool_15min": lambda r: _invert_for_rank(_nested_float(r["target_state_features"], "target_exhaustion_decay_state", "late_trend_risk_score_15min")),
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


def _session_position_state(index: int, closes: Sequence[float | None], highs: Sequence[float | None], lows: Sequence[float | None], vwaps: Sequence[float | None]) -> dict[str, Any]:
    minute_of_session = index
    close = closes[index]
    session_open = next((value for value in closes[: index + 1] if value is not None), None)
    high_values = _window_values(highs, index, index + 1)
    low_values = _window_values(lows, index, index + 1)
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


def _realized_vol(values: Sequence[float | None], index: int, window: int) -> float | None:
    if index < 1:
        return None
    returns: list[float] = []
    start = max(1, index - window + 1)
    for pos in range(start, index + 1):
        current = values[pos]
        previous = values[pos - 1]
        if current is not None and previous not in (None, 0):
            returns.append(math.log(current / previous))
    return pstdev(returns) if len(returns) >= 2 else None


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
    return None if not true_ranges else mean(true_ranges) / close


def _relative_to_window(values: Sequence[float | None], index: int, window: int) -> float | None:
    current = values[index]
    history = _window_values(values, index, window)
    if current is None or not history:
        return None
    avg = mean(history)
    return None if avg == 0 else current / avg


def _trend_quality_score(values: Sequence[float | None], index: int, window: int) -> float | None:
    ret = _window_return(values, index, window)
    stability = _path_stability_score(values, index, window)
    if ret is None and stability is None:
        return None
    direction_strength = None if ret is None else min(abs(math.tanh(ret / 0.03)), 1.0)
    return _average([direction_strength, stability])


def _path_stability_score(values: Sequence[float | None], index: int, window: int) -> float | None:
    returns = _incremental_returns(values, index, window)
    if len(returns) < 2:
        return None
    total_abs = sum(abs(value) for value in returns)
    net_abs = abs(sum(returns))
    efficiency = None if total_abs == 0 else net_abs / total_abs
    flips = _direction_flip_count(values, index, window)
    flip_penalty = None if flips is None else 1.0 - min(flips / max(len(returns) - 1, 1), 1.0)
    vol = pstdev(returns) if len(returns) >= 2 else None
    vol_stability = None if vol is None else 1.0 - min(vol / 0.02, 1.0)
    return _average([efficiency, flip_penalty, vol_stability])


def _incremental_returns(values: Sequence[float | None], index: int, window: int) -> list[float]:
    returns: list[float] = []
    start = max(1, index - window + 1)
    for pos in range(start, index + 1):
        current = values[pos]
        previous = values[pos - 1]
        if current is not None and previous not in (None, 0):
            returns.append(current / previous - 1.0)
    return returns


def _direction_flip_count(values: Sequence[float | None], index: int, window: int) -> int | None:
    returns = [value for value in _incremental_returns(values, index, window) if value != 0]
    if len(returns) < 2:
        return None
    signs = [1 if value > 0 else -1 for value in returns]
    return sum(1 for left, right in zip(signs, signs[1:]) if left != right)


def _time_since_last_direction_flip(values: Sequence[float | None], index: int) -> int | None:
    returns = _incremental_returns(values, index, index + 1)
    if len(returns) < 2:
        return None
    signs = [1 if value > 0 else -1 if value < 0 else 0 for value in returns]
    for offset in range(len(signs) - 1, 0, -1):
        if signs[offset] and signs[offset - 1] and signs[offset] != signs[offset - 1]:
            return len(signs) - offset
    return len(signs)


def _trend_age_bars(values: Sequence[float | None], index: int, window: int) -> int | None:
    returns = _incremental_returns(values, index, window)
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


def _state_persistence_score(values: Sequence[float | None], index: int, window: int) -> float | None:
    age = _trend_age_bars(values, index, window)
    if age is None:
        return None
    return min(age / max(window, 1), 1.0)


def _momentum_decay_score(values: Sequence[float | None], index: int, window: int) -> float | None:
    returns = _incremental_returns(values, index, window)
    if len(returns) < 4:
        return None
    midpoint = len(returns) // 2
    first = mean(abs(value) for value in returns[:midpoint])
    second = mean(abs(value) for value in returns[midpoint:])
    return None if first == 0 else max(0.0, min((first - second) / first, 1.0))


def _volume_exhaustion_score(volumes: Sequence[float | None], index: int, window: int) -> float | None:
    history = _window_values(volumes, index, window)
    current = volumes[index]
    if current is None or len(history) < 4:
        return None
    midpoint = len(history) // 2
    first = mean(history[:midpoint])
    second = mean(history[midpoint:])
    return None if first == 0 else max(0.0, min((first - second) / first, 1.0))


def _volatility_exhaustion_score(values: Sequence[float | None], index: int, window: int) -> float | None:
    returns = _incremental_returns(values, index, window)
    if len(returns) < 4:
        return None
    midpoint = len(returns) // 2
    first = pstdev(returns[:midpoint]) if len(returns[:midpoint]) >= 2 else None
    second = pstdev(returns[midpoint:]) if len(returns[midpoint:]) >= 2 else None
    if first in (None, 0) or second is None:
        return None
    return max(0.0, min((second - first) / first, 1.0))


def _late_trend_risk_score(values: Sequence[float | None], volumes: Sequence[float | None], index: int, window: int) -> float | None:
    return _average([
        _state_persistence_score(values, index, window),
        _momentum_decay_score(values, index, window),
        _volume_exhaustion_score(volumes, index, window),
        _volatility_exhaustion_score(values, index, window),
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
    return mean(clean) if clean else None


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


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
