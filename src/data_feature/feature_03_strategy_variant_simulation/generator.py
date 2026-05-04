"""Deterministic Layer 3 strategy variant simulation feature generator.

The generator consumes already-cleaned 1Min bars plus manager-supplied anonymous
candidate and reviewed strategy-variant specs. It performs no provider calls and
no database writes; SQL/request wrappers own runtime reads and writes.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
FEATURE = "feature_03_strategy_variant_simulation"
SUPPORTED_FAMILY = "moving_average_crossover"
DEFAULT_RUN_ID = "adhoc"
METADATA_COLUMNS = {
    "run_id",
    "available_time",
    "target_candidate_id",
    "strategy_family",
    "strategy_variant",
    "variant_spec_ref",
    "signal_state",
    "exposure",
}
PROFILE_WINDOWS = {
    "micro_3_10": (3, 10),
    "scalp_5_20": (5, 20),
    "fast_10_30": (10, 30),
    "intraday_30_120": (30, 120),
    "intraday_90_360": (90, 360),
    "intraday_240_960": (240, 960),
    "equity_day_390_1950": (390, 1950),
    "continuous_day_1440_7200": (1440, 7200),
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


@dataclass(frozen=True)
class Candidate:
    target_candidate_id: str
    symbol: str


@dataclass(frozen=True)
class MovingAverageCrossoverParams:
    ma_window_profile: str
    fast_window_1min_bars: int
    slow_window_1min_bars: int
    price_field: str
    ma_type: str
    crossover_confirmation_bars: int
    cooldown_bars: int
    min_slope: float


@dataclass(frozen=True)
class StrategyVariant:
    strategy_family: str
    strategy_variant: str
    variant_spec_ref: str
    params: MovingAverageCrossoverParams


@dataclass(frozen=True)
class SimulationInputs:
    bars_by_candidate: dict[str, list[Bar]]
    variants: list[StrategyVariant]


class StrategyVariantSimulationError(ValueError):
    """Raised when feature_03 simulation inputs are invalid."""


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [{str(k): str(v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def read_json_rows(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("rows", "target_candidates", "strategy_variants", "variants"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise StrategyVariantSimulationError(f"{path} must contain a JSON list or an object with a rows/variants key")
    return [dict(item) for item in payload]


def build_inputs(
    *,
    bar_rows: Iterable[Mapping[str, Any]],
    candidate_rows: Iterable[Mapping[str, Any]],
    variant_rows: Iterable[Mapping[str, Any]],
) -> SimulationInputs:
    candidates = _candidate_map(candidate_rows)
    bars_by_candidate: dict[str, list[Bar]] = {}
    for row in bar_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        target_candidate_id = str(row.get("target_candidate_id") or "").strip()
        if not target_candidate_id and symbol:
            target_candidate_id = candidates.get(symbol, "")
        if not target_candidate_id or not symbol:
            continue
        timestamp = _parse_timestamp(row.get("timestamp") or row.get("available_time"))
        bar = Bar(
            target_candidate_id=target_candidate_id,
            symbol=symbol,
            timestamp=timestamp,
            available_time=_parse_timestamp(row.get("available_time") or timestamp.isoformat()),
            open=_safe_float(row.get("bar_open")),
            high=_safe_float(row.get("bar_high")),
            low=_safe_float(row.get("bar_low")),
            close=_safe_float(row.get("bar_close")),
            volume=_safe_float(row.get("bar_volume")),
        )
        bars_by_candidate.setdefault(target_candidate_id, []).append(bar)

    for target_candidate_id, bars in bars_by_candidate.items():
        bars_by_candidate[target_candidate_id] = sorted(bars, key=lambda item: (item.available_time, item.timestamp))

    variants = [_variant(row) for row in variant_rows]
    if not variants:
        raise StrategyVariantSimulationError("at least one strategy variant is required")
    return SimulationInputs(bars_by_candidate=bars_by_candidate, variants=variants)


def generate_rows(inputs: SimulationInputs, *, run_id: str = DEFAULT_RUN_ID) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in inputs.variants:
        for target_candidate_id in sorted(inputs.bars_by_candidate):
            rows.extend(simulate_variant(inputs.bars_by_candidate[target_candidate_id], variant, run_id=run_id))
    return rows


def simulate_variant(bars: Sequence[Bar], variant: StrategyVariant, *, run_id: str = DEFAULT_RUN_ID) -> list[dict[str, Any]]:
    if variant.strategy_family != SUPPORTED_FAMILY:
        raise StrategyVariantSimulationError(f"unsupported strategy_family: {variant.strategy_family}")
    if not bars:
        return []

    prices = [_price(bar, variant.params.price_field) for bar in bars]
    fast_ma = _moving_average_series(prices, variant.params.fast_window_1min_bars, variant.params.ma_type)
    slow_ma = _moving_average_series(prices, variant.params.slow_window_1min_bars, variant.params.ma_type)

    rows: list[dict[str, Any]] = []
    exposure = 0
    bars_since_signal = 10**9
    previous_close: float | None = None
    for index, bar in enumerate(bars):
        current_close = bar.close
        close_to_close_return = _safe_return(current_close, previous_close)
        exposure_before_bar = exposure
        variant_return = None if close_to_close_return is None else exposure_before_bar * close_to_close_return

        desired_exposure = _desired_exposure(index, fast_ma, slow_ma, variant.params)
        signal_state = "hold_flat" if exposure == 0 else ("hold_long" if exposure > 0 else "hold_short")
        entry_state = "none"
        exit_state = "none"
        if desired_exposure is not None and desired_exposure != exposure and bars_since_signal >= variant.params.cooldown_bars:
            if exposure != 0 and desired_exposure == 0:
                exit_state = "exit_long" if exposure > 0 else "exit_short"
            elif exposure == 0 and desired_exposure != 0:
                entry_state = "enter_long" if desired_exposure > 0 else "enter_short"
            else:
                exit_state = "reverse_from_long" if exposure > 0 else "reverse_from_short"
                entry_state = "enter_long" if desired_exposure > 0 else "enter_short"
            exposure = desired_exposure
            bars_since_signal = 0
            signal_state = "long" if exposure > 0 else ("short" if exposure < 0 else "flat")
        else:
            bars_since_signal += 1

        rows.append(
            {
                "run_id": run_id,
                "available_time": bar.available_time.isoformat(),
                "target_candidate_id": bar.target_candidate_id,
                "strategy_family": variant.strategy_family,
                "strategy_variant": variant.strategy_variant,
                "variant_spec_ref": variant.variant_spec_ref,
                "signal_state": signal_state,
                "exposure": exposure,
                "exposure_before_bar": exposure_before_bar,
                "entry_state": entry_state,
                "exit_state": exit_state,
                "holding_bars": 0 if exposure == 0 else bars_since_signal,
                "price_field_value": prices[index],
                "fast_ma": fast_ma[index],
                "slow_ma": slow_ma[index],
                "ma_delta": None if fast_ma[index] is None or slow_ma[index] is None else fast_ma[index] - slow_ma[index],
                "close_to_close_return": close_to_close_return,
                "variant_return": variant_return,
            }
        )
        previous_close = current_close
    return rows


def payload_columns(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted({key for row in rows for key in row if key not in METADATA_COLUMNS})


def _candidate_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    candidates: dict[str, str] = {}
    for row in rows:
        target_candidate_id = str(row.get("target_candidate_id") or row.get("candidate_id") or "").strip()
        symbol = str(row.get("symbol") or row.get("routing_symbol") or "").strip().upper()
        if target_candidate_id and symbol:
            candidates[symbol] = target_candidate_id
    return candidates


def _variant(row: Mapping[str, Any]) -> StrategyVariant:
    strategy_family = str(row.get("strategy_family") or row.get("3_strategy_family") or "").strip()
    if strategy_family != SUPPORTED_FAMILY:
        raise StrategyVariantSimulationError(f"unsupported or missing strategy_family: {strategy_family!r}")
    strategy_variant = str(row.get("strategy_variant") or row.get("3_strategy_variant") or row.get("variant_id") or "").strip()
    if not strategy_variant:
        raise StrategyVariantSimulationError("strategy_variant is required")
    variant_spec_ref = str(row.get("variant_spec_ref") or row.get("spec_ref") or strategy_variant).strip()
    params_payload = row.get("params") or row.get("variant_params") or {}
    if isinstance(params_payload, str) and params_payload.strip():
        params = json.loads(params_payload)
    elif isinstance(params_payload, Mapping):
        params = dict(params_payload)
    else:
        params = {}
    params.update({key: value for key, value in row.items() if key in {"ma_window_profile", "price_field", "ma_type", "crossover_confirmation_bars", "cooldown_bars", "min_slope", "fast_window_1min_bars", "slow_window_1min_bars"}})
    return StrategyVariant(strategy_family=strategy_family, strategy_variant=strategy_variant, variant_spec_ref=variant_spec_ref, params=_ma_params(params))


def _ma_params(params: Mapping[str, Any]) -> MovingAverageCrossoverParams:
    profile_value = params.get("ma_window_profile")
    profile_id, fast_window, slow_window = _profile_windows(profile_value, params)
    price_field = str(params.get("price_field") or "bar_close").strip()
    if price_field not in {"bar_close", "bar_hlc3"}:
        raise StrategyVariantSimulationError(f"unsupported price_field: {price_field}")
    ma_type = str(params.get("ma_type") or "ema").strip().lower()
    if ma_type not in {"ema", "sma"}:
        raise StrategyVariantSimulationError(f"unsupported ma_type: {ma_type}")
    return MovingAverageCrossoverParams(
        ma_window_profile=profile_id,
        fast_window_1min_bars=fast_window,
        slow_window_1min_bars=slow_window,
        price_field=price_field,
        ma_type=ma_type,
        crossover_confirmation_bars=max(1, int(params.get("crossover_confirmation_bars") or 1)),
        cooldown_bars=max(0, int(params.get("cooldown_bars") or 0)),
        min_slope=max(0.0, float(params.get("min_slope") or 0.0)),
    )


def _profile_windows(profile_value: Any, params: Mapping[str, Any]) -> tuple[str, int, int]:
    if isinstance(profile_value, (list, tuple)) and len(profile_value) >= 3:
        return str(profile_value[0]), int(profile_value[1]), int(profile_value[2])
    profile_id = str(profile_value or "").strip()
    if profile_id in PROFILE_WINDOWS:
        fast, slow = PROFILE_WINDOWS[profile_id]
        return profile_id, fast, slow
    fast = params.get("fast_window_1min_bars")
    slow = params.get("slow_window_1min_bars")
    if fast and slow:
        return profile_id or f"custom_{fast}_{slow}", int(fast), int(slow)
    raise StrategyVariantSimulationError("ma_window_profile or fast/slow windows are required")


def _desired_exposure(index: int, fast_ma: Sequence[float | None], slow_ma: Sequence[float | None], params: MovingAverageCrossoverParams) -> int | None:
    confirmation = params.crossover_confirmation_bars
    if index < confirmation:
        return None
    deltas = [_delta(fast_ma[pos], slow_ma[pos]) for pos in range(index - confirmation + 1, index + 1)]
    previous_delta = _delta(fast_ma[index - confirmation], slow_ma[index - confirmation])
    if previous_delta is None or any(delta is None for delta in deltas):
        return None
    slope = _normalized_slope(fast_ma[index], fast_ma[index - 1])
    if slope is None or abs(slope) < params.min_slope:
        return None
    if previous_delta <= 0 and all(float(delta) > 0 for delta in deltas):
        return 1
    if previous_delta >= 0 and all(float(delta) < 0 for delta in deltas):
        return -1
    return None


def _moving_average_series(values: Sequence[float | None], window: int, ma_type: str) -> list[float | None]:
    if window <= 0:
        raise StrategyVariantSimulationError("moving-average windows must be positive")
    if ma_type == "sma":
        return [_sma(values, index, window) for index in range(len(values))]
    return _ema_series(values, window)


def _sma(values: Sequence[float | None], index: int, window: int) -> float | None:
    if index + 1 < window:
        return None
    slice_values = values[index - window + 1 : index + 1]
    if any(value is None for value in slice_values):
        return None
    return sum(float(value) for value in slice_values) / window


def _ema_series(values: Sequence[float | None], window: int) -> list[float | None]:
    alpha = 2 / (window + 1)
    ema: float | None = None
    output: list[float | None] = []
    clean_count = 0
    for value in values:
        if value is None:
            output.append(None)
            continue
        clean_count += 1
        ema = float(value) if ema is None else alpha * float(value) + (1 - alpha) * ema
        output.append(ema if clean_count >= window else None)
    return output


def _price(bar: Bar, price_field: str) -> float | None:
    if price_field == "bar_hlc3":
        if bar.high is None or bar.low is None or bar.close is None:
            return None
        return (bar.high + bar.low + bar.close) / 3
    return bar.close


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise StrategyVariantSimulationError("timestamp is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET)


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _safe_return(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return current / previous - 1


def _delta(fast: float | None, slow: float | None) -> float | None:
    if fast is None or slow is None:
        return None
    return fast - slow


def _normalized_slope(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return current / previous - 1
