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
DEFAULT_VECTOR_VERSION = "target_state_vector_v1"
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
    "target_state_vector_version",
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
    target_state_vector_version: str = DEFAULT_VECTOR_VERSION,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target_candidate_id in sorted(inputs.bars_by_candidate):
        rows.extend(
            generate_candidate_rows(
                inputs.bars_by_candidate[target_candidate_id],
                inputs.market_context_rows,
                inputs.sector_context_rows,
                run_id=run_id,
                target_state_vector_version=target_state_vector_version,
            )
        )
    return rows


def generate_candidate_rows(
    bars: Sequence[Bar],
    market_context_rows: Sequence[ContextRow] = (),
    sector_context_rows: Sequence[ContextRow] = (),
    *,
    run_id: str = DEFAULT_RUN_ID,
    target_state_vector_version: str = DEFAULT_VECTOR_VERSION,
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
                "target_state_vector_version": target_state_vector_version,
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
            "sector_relative_strength_state",
            "sector_trend_stability_state",
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
        "target_return_shape": {},
        "target_trend_momentum_state": {},
        "target_volatility_range_state": {},
        "target_gap_jump_state": {},
        "target_volume_activity_state": {},
        "target_liquidity_cost_state": {},
        "target_vwap_location_state": {},
        "target_session_position_state": {},
        "target_data_quality_state": {},
    }
    for window in STATE_WINDOWS:
        state["target_return_shape"][f"return_{window}min"] = _window_return(closes, index, window)
        state["target_volatility_range_state"][f"realized_vol_{window}min"] = _realized_vol(closes, index, window)
        state["target_volatility_range_state"][f"range_position_{window}min"] = _range_position(closes, highs, lows, index, window)
        state["target_volatility_range_state"][f"atr_pct_{window}min"] = _atr_pct(closes, highs, lows, index, window)
        state["target_volume_activity_state"][f"relative_volume_{window}min"] = _relative_to_window(volumes, index, window)
        state["target_volume_activity_state"][f"relative_dollar_volume_{window}min"] = _relative_to_window(dollar_volumes, index, window)

    state["target_trend_momentum_state"]["return_5m_minus_15m"] = _delta(
        state["target_return_shape"].get("return_5min"),
        state["target_return_shape"].get("return_15min"),
    )
    state["target_trend_momentum_state"]["return_15m_minus_60m"] = _delta(
        state["target_return_shape"].get("return_15min"),
        state["target_return_shape"].get("return_60min"),
    )
    state["target_gap_jump_state"]["current_bar_return"] = _window_return(closes, index, 1)
    state["target_gap_jump_state"]["current_range_pct"] = None if close in (None, 0) or highs[index] is None or lows[index] is None else (highs[index] - lows[index]) / close
    state["target_liquidity_cost_state"]["spread_bps"] = spreads[index]
    state["target_liquidity_cost_state"]["dollar_volume"] = dollar_volumes[index]
    state["target_vwap_location_state"]["vwap_distance_pct"] = _safe_ratio_delta(close, vwaps[index])
    state["target_session_position_state"]["window_policy"] = "completed_1min_bars"
    state["target_data_quality_state"]["has_close"] = close is not None
    state["target_data_quality_state"]["has_high_low"] = highs[index] is not None and lows[index] is not None
    state["target_data_quality_state"]["has_volume"] = volumes[index] is not None
    state["target_data_quality_state"]["history_bars"] = index + 1
    return state


def _cross_state_features(target_state: Mapping[str, Any], market_state: Mapping[str, Any], sector_state: Mapping[str, Any]) -> dict[str, Any]:
    target_return = _nested_float(target_state, "target_return_shape", "return_15min")
    target_vol = _nested_float(target_state, "target_volatility_range_state", "realized_vol_15min")
    market_payload = market_state.get("market_context_payload") if isinstance(market_state.get("market_context_payload"), Mapping) else {}
    sector_payload = sector_state.get("sector_context_payload") if isinstance(sector_state.get("sector_context_payload"), Mapping) else {}
    market_return = _first_float(market_payload, "market_return_15min", "market_return", "return_15min", "relative_strength_return")
    sector_return = _first_float(sector_payload, "sector_return_15min", "sector_return", "return_15min", "relative_strength_return")
    market_vol = _first_float(market_payload, "market_volatility_15min", "market_volatility", "realized_vol_15min")
    sector_vol = _first_float(sector_payload, "sector_volatility_15min", "sector_volatility", "realized_vol_15min", "relative_strength_realized_vol_20d_ratio")
    return {
        "state_observation_windows": list(STATE_WINDOW_LABELS),
        "state_window_sync_policy": STATE_WINDOW_SYNC_POLICY,
        "target_vs_market_strength": _delta(target_return, market_return),
        "target_vs_sector_strength": _delta(target_return, sector_return),
        "target_vs_market_volatility": _safe_div(target_vol, market_vol),
        "target_vs_sector_volatility": _safe_div(target_vol, sector_vol),
        "target_market_beta_correlation": None,
        "target_sector_beta_correlation": None,
        "sector_confirmation_state": _sector_confirmation(target_return, sector_return),
        "idiosyncratic_residual_state": _delta(_delta(target_return, market_return), sector_return),
        "relative_liquidity_cost_state": None,
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
