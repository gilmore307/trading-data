"""Deterministic Layer 3 strategy selection feature generator.

The generator consumes already-cleaned 1Min bars plus manager-supplied anonymous
candidate rows and reviewed strategy-variant specs from ``trading-model``. It
performs no provider calls and no database writes; SQL/request wrappers own
runtime reads and writes.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
FEATURE = "feature_03_strategy_selection"
DEFAULT_RUN_ID = "adhoc"
METADATA_COLUMNS = {
    "run_id",
    "available_time",
    "target_candidate_id",
    "3_strategy_family",
    "3_strategy_variant",
    "variant_spec_ref",
    "signal_state",
    "exposure",
}
SUPPORTED_FAMILIES = {
    "moving_average_crossover",
    "donchian_channel_breakout",
    "macd_trend",
    "bollinger_band_reversion",
    "rsi_reversion",
    "bias_reversion",
    "vwap_reversion",
    "range_breakout",
    "opening_range_breakout",
    "volatility_breakout",
}
PROFILE_VALUES = {
    "ma_window_profile": {
        "micro_3_10": ("micro_3_10", 3, 10),
        "scalp_5_20": ("scalp_5_20", 5, 20),
        "fast_10_30": ("fast_10_30", 10, 30),
        "intraday_30_120": ("intraday_30_120", 30, 120),
        "intraday_90_360": ("intraday_90_360", 90, 360),
        "intraday_240_960": ("intraday_240_960", 240, 960),
        "equity_day_390_1950": ("equity_day_390_1950", 390, 1950),
        "continuous_day_1440_7200": ("continuous_day_1440_7200", 1440, 7200),
        "micro_10": ("micro_10", 10),
        "scalp_20": ("scalp_20", 20),
        "fast_30": ("fast_30", 30),
        "intraday_60": ("intraday_60", 60),
        "intraday_120": ("intraday_120", 120),
        "intraday_240": ("intraday_240", 240),
        "equity_day_390": ("equity_day_390", 390),
        "continuous_day_1440": ("continuous_day_1440", 1440),
    },
    "channel_window_profile": {
        "micro_10_5_atr10": ("micro_10_5_atr10", 10, 5, 10),
        "scalp_20_10_atr14": ("scalp_20_10_atr14", 20, 10, 14),
        "fast_30_15_atr20": ("fast_30_15_atr20", 30, 15, 20),
        "intraday_60_30_atr30": ("intraday_60_30_atr30", 60, 30, 30),
        "intraday_120_60_atr60": ("intraday_120_60_atr60", 120, 60, 60),
        "intraday_240_120_atr120": ("intraday_240_120_atr120", 240, 120, 120),
        "equity_day_390_195_atr195": ("equity_day_390_195_atr195", 390, 195, 195),
        "continuous_day_1440_720_atr720": ("continuous_day_1440_720_atr720", 1440, 720, 720),
    },
    "macd_profile": {
        "micro_3_10_3": ("micro_3_10_3", 3, 10, 3),
        "scalp_5_20_5": ("scalp_5_20_5", 5, 20, 5),
        "fast_8_21_5": ("fast_8_21_5", 8, 21, 5),
        "intraday_12_26_9": ("intraday_12_26_9", 12, 26, 9),
        "intraday_24_52_18": ("intraday_24_52_18", 24, 52, 18),
        "intraday_60_180_45": ("intraday_60_180_45", 60, 180, 45),
        "intraday_120_360_90": ("intraday_120_360_90", 120, 360, 90),
        "intraday_240_720_180": ("intraday_240_720_180", 240, 720, 180),
        "equity_day_390_1014_351": ("equity_day_390_1014_351", 390, 1014, 351),
        "equity_swing_1950_5070_1755": ("equity_swing_1950_5070_1755", 1950, 5070, 1755),
        "continuous_day_1440_3744_1296": ("continuous_day_1440_3744_1296", 1440, 3744, 1296),
        "continuous_swing_7200_18720_6480": ("continuous_swing_7200_18720_6480", 7200, 18720, 6480),
    },
    "band_window_profile": {},
    "rsi_period_profile": {},
    "range_window_profile": {},
    "volatility_profile": {
        "micro_atr10_x1.25": ("micro_atr10_x1.25", "ATR", 10, 1.25),
        "scalp_atr14_x1.5": ("scalp_atr14_x1.5", "ATR", 14, 1.5),
        "fast_atr20_x1.5": ("fast_atr20_x1.5", "ATR", 20, 1.5),
        "intraday_atr60_x1.5": ("intraday_atr60_x1.5", "ATR", 60, 1.5),
        "intraday_atr120_x2.0": ("intraday_atr120_x2.0", "ATR", 120, 2.0),
        "intraday_hv240_x1.5": ("intraday_hv240_x1.5", "HV", 240, 1.5),
        "equity_day_atr390_x1.5": ("equity_day_atr390_x1.5", "ATR", 390, 1.5),
        "continuous_day_hv1440_x2.0": ("continuous_day_hv1440_x2.0", "HV", 1440, 2.0),
    },
}
for _key in ("band_window_profile", "range_window_profile"):
    PROFILE_VALUES[_key] = {key: value for key, value in PROFILE_VALUES["ma_window_profile"].items() if len(value) == 2}
PROFILE_VALUES["rsi_period_profile"] = {
    "micro_5": ("micro_5", 5),
    "fast_7": ("fast_7", 7),
    "scalp_14": ("scalp_14", 14),
    "intraday_30": ("intraday_30", 30),
    "intraday_60": ("intraday_60", 60),
    "intraday_120": ("intraday_120", 120),
    "equity_day_390": ("equity_day_390", 390),
    "continuous_day_1440": ("continuous_day_1440", 1440),
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
class StrategyVariant:
    strategy_family: str
    strategy_variant: str
    variant_spec_ref: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class SimulationInputs:
    bars_by_candidate: dict[str, list[Bar]]
    variants: list[StrategyVariant]


class StrategySelectionError(ValueError):
    """Raised when feature_03 strategy-selection inputs are invalid."""


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
        raise StrategySelectionError(f"{path} must contain a JSON list or an object with a rows/variants key")
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
        target_candidate_id = str(row.get("target_candidate_id") or "").strip() or candidates.get(symbol, "")
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
            bar_vwap=_safe_float(row.get("bar_vwap")),
            dollar_volume=_safe_float(row.get("dollar_volume")),
            spread_bps=_safe_float(row.get("spread_bps")),
        )
        bars_by_candidate.setdefault(target_candidate_id, []).append(bar)

    for target_candidate_id, bars in bars_by_candidate.items():
        bars_by_candidate[target_candidate_id] = sorted(bars, key=lambda item: (item.available_time, item.timestamp))

    variants = [_variant(row) for row in variant_rows]
    if not variants:
        raise StrategySelectionError("at least one strategy variant is required")
    return SimulationInputs(bars_by_candidate=bars_by_candidate, variants=variants)


def generate_rows(inputs: SimulationInputs, *, run_id: str = DEFAULT_RUN_ID) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in inputs.variants:
        for target_candidate_id in sorted(inputs.bars_by_candidate):
            rows.extend(simulate_variant(inputs.bars_by_candidate[target_candidate_id], variant, run_id=run_id))
    return rows


def simulate_variant(bars: Sequence[Bar], variant: StrategyVariant, *, run_id: str = DEFAULT_RUN_ID) -> list[dict[str, Any]]:
    if variant.strategy_family not in SUPPORTED_FAMILIES:
        raise StrategySelectionError(f"unsupported strategy_family: {variant.strategy_family}")
    if not bars:
        return []

    context = _build_context(bars, variant)
    rows: list[dict[str, Any]] = []
    exposure = 0
    holding_bars = 0
    bars_since_signal = 10**9
    previous_close: float | None = None
    for index, bar in enumerate(bars):
        close_to_close_return = _safe_return(bar.close, previous_close)
        exposure_before_bar = exposure
        variant_return = None if close_to_close_return is None else exposure_before_bar * close_to_close_return
        desired_exposure, reason, diagnostics = _family_signal(index, bars, variant, context, exposure, holding_bars)
        signal_state = "hold_flat" if exposure == 0 else ("hold_long" if exposure > 0 else "hold_short")
        entry_state = "none"
        exit_state = "none"
        cooldown = _int_param(variant.params, "cooldown_bars", 1, minimum=0)
        if desired_exposure is not None and desired_exposure != exposure and bars_since_signal >= cooldown:
            if exposure != 0 and desired_exposure == 0:
                exit_state = "exit_long" if exposure > 0 else "exit_short"
            elif exposure == 0 and desired_exposure != 0:
                entry_state = "enter_long" if desired_exposure > 0 else "enter_short"
            else:
                exit_state = "reverse_from_long" if exposure > 0 else "reverse_from_short"
                entry_state = "enter_long" if desired_exposure > 0 else "enter_short"
            exposure = desired_exposure
            bars_since_signal = 0
            holding_bars = 0 if exposure == 0 else 1
            signal_state = "long" if exposure > 0 else ("short" if exposure < 0 else "flat")
        else:
            bars_since_signal += 1
            holding_bars = holding_bars + 1 if exposure else 0

        rows.append(
            {
                "run_id": run_id,
                "available_time": bar.available_time.isoformat(),
                "target_candidate_id": bar.target_candidate_id,
                "3_strategy_family": variant.strategy_family,
                "3_strategy_variant": variant.strategy_variant,
                "variant_spec_ref": variant.variant_spec_ref,
                "signal_state": signal_state,
                "exposure": exposure,
                "exposure_before_bar": exposure_before_bar,
                "entry_state": entry_state,
                "exit_state": exit_state,
                "holding_bars": holding_bars,
                "signal_reason": reason,
                "close_to_close_return": close_to_close_return,
                "variant_return": variant_return,
                **diagnostics,
            }
        )
        previous_close = bar.close
    return rows


def payload_columns(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted({key for row in rows for key in row if key not in METADATA_COLUMNS})


def _build_context(bars: Sequence[Bar], variant: StrategyVariant) -> dict[str, Any]:
    prices = [_price(bar, str(variant.params.get("price_field") or "bar_close")) for bar in bars]
    closes = [bar.close for bar in bars]
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    volumes = [bar.volume for bar in bars]
    atr14 = _atr_series(highs, lows, closes, 14)
    return {
        "prices": prices,
        "closes": closes,
        "highs": highs,
        "lows": lows,
        "volumes": volumes,
        "atr14": atr14,
        **_family_context(bars, variant, prices, closes, highs, lows, volumes),
    }


def _family_context(bars: Sequence[Bar], variant: StrategyVariant, prices: Sequence[float | None], closes: Sequence[float | None], highs: Sequence[float | None], lows: Sequence[float | None], volumes: Sequence[float | None]) -> dict[str, Any]:
    family = variant.strategy_family
    params = variant.params
    if family == "moving_average_crossover":
        _, fast, slow = _profile(params, "ma_window_profile", min_values=3)
        ma_type = str(params.get("ma_type") or "ema").lower()
        return {"fast_ma": _moving_average_series(prices, fast, ma_type), "slow_ma": _moving_average_series(prices, slow, ma_type)}
    if family == "donchian_channel_breakout":
        _, entry, exit_window, atr_window = _profile(params, "channel_window_profile", min_values=4)
        return {"entry_high": _rolling_high(highs, entry, exclude_current=True), "entry_low": _rolling_low(lows, entry, exclude_current=True), "exit_high": _rolling_high(highs, exit_window, exclude_current=True), "exit_low": _rolling_low(lows, exit_window, exclude_current=True), "atr": _atr_series(highs, lows, closes, atr_window)}
    if family == "macd_trend":
        _, fast, slow, signal = _profile(params, "macd_profile", min_values=4)
        fast_ema = _moving_average_series(prices, fast, "ema")
        slow_ema = _moving_average_series(prices, slow, "ema")
        macd = [None if f is None or s is None else f - s for f, s in zip(fast_ema, slow_ema, strict=True)]
        signal_line = _moving_average_series(macd, signal, "ema")
        hist = [None if m is None or s is None else m - s for m, s in zip(macd, signal_line, strict=True)]
        return {"macd": macd, "macd_signal": signal_line, "macd_hist": hist, "atr": _atr_series(highs, lows, closes, max(14, slow))}
    if family == "bollinger_band_reversion":
        _, window = _profile(params, "band_window_profile", min_values=2)
        center = _moving_average_series(prices, window, "sma")
        std = _rolling_std(prices, window)
        return {"band_center": center, "band_std": std, "trend_ma": _moving_average_series(prices, min(max(window, 3), len(prices) or window), "sma")}
    if family == "rsi_reversion":
        _, period = _profile(params, "rsi_period_profile", min_values=2)
        return {"rsi": _rsi_series(prices, period), "long_rsi": _rsi_series(prices, max(period * 2, period + 1))}
    if family == "bias_reversion":
        _, window = _profile(params, "ma_window_profile", min_values=2)
        ma_type = str(params.get("ma_type") or "sma").lower()
        ma = _moving_average_series(prices, window, ma_type)
        std = _rolling_std(prices, window)
        return {"bias_ma": ma, "bias_std": std}
    if family == "vwap_reversion":
        return {"session_vwap": _session_vwap(bars), "vwap_std": _rolling_std(prices, 20)}
    if family == "range_breakout":
        _, window = _profile(params, "range_window_profile", min_values=2)
        return {"range_high": _rolling_high(highs, window, exclude_current=True), "range_low": _rolling_low(lows, window, exclude_current=True), "atr": _atr_series(highs, lows, closes, max(14, window)), "avg_volume": _moving_average_series(volumes, window, "sma")}
    if family == "opening_range_breakout":
        return _opening_range_context(bars)
    if family == "volatility_breakout":
        _, measure, window, threshold = _volatility_profile(params)
        if str(measure).upper() == "HV":
            vol = _rolling_std(_returns(closes), int(window))
        else:
            vol = _atr_series(highs, lows, closes, int(window))
        return {"volatility": vol, "volatility_avg": _moving_average_series(vol, int(window), "sma"), "volatility_threshold": float(threshold), "trend_ma": _moving_average_series(prices, max(3, min(int(window), 60)), "sma"), "range_high": _rolling_high(highs, int(window), exclude_current=True), "range_low": _rolling_low(lows, int(window), exclude_current=True)}
    return {}


def _family_signal(index: int, bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], exposure: int, holding_bars: int) -> tuple[int | None, str, dict[str, Any]]:
    return {
        "moving_average_crossover": _signal_ma_crossover,
        "donchian_channel_breakout": _signal_donchian,
        "macd_trend": _signal_macd,
        "bollinger_band_reversion": _signal_bollinger,
        "rsi_reversion": _signal_rsi,
        "bias_reversion": _signal_bias,
        "vwap_reversion": _signal_vwap,
        "range_breakout": _signal_range_breakout,
        "opening_range_breakout": _signal_opening_range,
        "volatility_breakout": _signal_volatility_breakout,
    }[variant.strategy_family](index, bars, variant, context, exposure, holding_bars)


def _signal_ma_crossover(index: int, _bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], _exposure: int, _holding: int) -> tuple[int | None, str, dict[str, Any]]:
    fast = context["fast_ma"]
    slow = context["slow_ma"]
    confirmation = _int_param(variant.params, "crossover_confirmation_bars", 1, minimum=1)
    min_slope = _float_param(variant.params, "min_slope", 0.0, minimum=0.0)
    desired = _confirmed_cross(index, fast, slow, confirmation, min_slope)
    return desired, "ma_crossover" if desired is not None else "none", {"fast_ma": fast[index], "slow_ma": slow[index], "ma_delta": _delta(fast[index], slow[index])}


def _signal_donchian(index: int, bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], exposure: int, _holding: int) -> tuple[int | None, str, dict[str, Any]]:
    close = bars[index].close
    atr = context["atr"][index]
    high = context["entry_high"][index]
    low = context["entry_low"][index]
    buffer = _float_param(variant.params, "breakout_buffer_atr", 0.0) * (atr or 0)
    diagnostics = {"entry_channel_high": high, "entry_channel_low": low, "atr": atr, "stop_atr_multiple": _float_param(variant.params, "stop_atr_multiple", 0.0)}
    if close is None or high is None or low is None or atr is None:
        return None, "insufficient_history", diagnostics
    if close > high + buffer:
        return 1, "donchian_upper_break", diagnostics
    if close < low - buffer:
        return -1, "donchian_lower_break", diagnostics
    if exposure > 0 and context["exit_low"][index] is not None and close < context["exit_low"][index]:
        return 0, "donchian_long_exit", diagnostics
    if exposure < 0 and context["exit_high"][index] is not None and close > context["exit_high"][index]:
        return 0, "donchian_short_exit", diagnostics
    return None, "none", diagnostics


def _signal_macd(index: int, _bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], exposure: int, _holding: int) -> tuple[int | None, str, dict[str, Any]]:
    macd = context["macd"][index]
    signal = context["macd_signal"][index]
    hist = context["macd_hist"][index]
    atr = context["atr"][index]
    threshold = 0.0 if str(variant.params.get("histogram_threshold") or "0") == "0" else 0.25 * (atr or 0)
    confirmation = _int_param(variant.params, "slope_confirmation_bars", 1, minimum=1)
    diagnostics = {"macd": macd, "macd_signal": signal, "macd_hist": hist, "histogram_threshold_value": threshold}
    if macd is None or signal is None or hist is None or index < confirmation:
        return None, "insufficient_history", diagnostics
    recent = [context["macd_hist"][pos] for pos in range(index - confirmation + 1, index + 1)]
    if any(value is None for value in recent):
        return None, "insufficient_history", diagnostics
    zero_ok_long = not variant.params.get("zero_line_filter") or macd > 0
    zero_ok_short = not variant.params.get("zero_line_filter") or macd < 0
    if all(float(value) > threshold for value in recent) and zero_ok_long:
        return 1, "macd_histogram_long", diagnostics
    if all(float(value) < -threshold for value in recent) and zero_ok_short:
        return -1, "macd_histogram_short", diagnostics
    if variant.params.get("exit_on_signal_cross") and exposure > 0 and macd < signal:
        return 0, "macd_long_exit", diagnostics
    if variant.params.get("exit_on_signal_cross") and exposure < 0 and macd > signal:
        return 0, "macd_short_exit", diagnostics
    return None, "none", diagnostics


def _signal_bollinger(index: int, bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], exposure: int, holding: int) -> tuple[int | None, str, dict[str, Any]]:
    price = bars[index].close
    center = context["band_center"][index]
    std = context["band_std"][index]
    mult = _float_param(variant.params, "band_stddev", 2.0)
    max_hold = _int_param(variant.params, "max_hold_minutes", 120, minimum=1)
    diagnostics = {"band_center": center, "band_std": std, "upper_band": None if center is None or std is None else center + mult * std, "lower_band": None if center is None or std is None else center - mult * std}
    if price is None or center is None or std in (None, 0):
        return None, "insufficient_history", diagnostics
    upper = center + mult * std
    lower = center - mult * std
    if exposure and holding >= max_hold:
        return 0, "max_hold_exit", diagnostics
    exit_band = str(variant.params.get("exit_band") or "midline")
    if exposure > 0 and (price >= center if exit_band == "midline" else price >= center - 0.5 * std):
        return 0, "bollinger_long_exit", diagnostics
    if exposure < 0 and (price <= center if exit_band == "midline" else price <= center + 0.5 * std):
        return 0, "bollinger_short_exit", diagnostics
    if _trend_filter_blocks(index, price, context.get("trend_ma"), variant.params):
        return None, "trend_filter_block", diagnostics
    entry_band = str(variant.params.get("entry_band") or "outer_touch")
    long_touch = bars[index].low is not None and bars[index].low <= lower if entry_band == "outer_touch" else price < lower
    short_touch = bars[index].high is not None and bars[index].high >= upper if entry_band == "outer_touch" else price > upper
    if long_touch:
        return 1, "bollinger_lower_reversion", diagnostics
    if short_touch:
        return -1, "bollinger_upper_reversion", diagnostics
    return None, "none", diagnostics


def _signal_rsi(index: int, bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], exposure: int, _holding: int) -> tuple[int | None, str, dict[str, Any]]:
    rsi = context["rsi"][index]
    oversold, overbought = _threshold_pair(variant.params)
    diagnostics = {"rsi": rsi, "oversold_threshold": oversold, "overbought_threshold": overbought, "long_rsi": context["long_rsi"][index]}
    if rsi is None:
        return None, "insufficient_history", diagnostics
    if exposure > 0 and _rsi_exit_long(rsi, str(variant.params.get("exit_midline") or "50_cross")):
        return 0, "rsi_long_exit", diagnostics
    if exposure < 0 and _rsi_exit_short(rsi, str(variant.params.get("exit_midline") or "50_cross")):
        return 0, "rsi_short_exit", diagnostics
    if variant.params.get("multi_duration_confirm") and context["long_rsi"][index] is None:
        return None, "multi_duration_missing", diagnostics
    if rsi <= oversold and _rsi_entry_allowed(index, bars, context, long_side=True, divergence=bool(variant.params.get("divergence_required"))):
        return 1, "rsi_oversold_reversion", diagnostics
    if rsi >= overbought and _rsi_entry_allowed(index, bars, context, long_side=False, divergence=bool(variant.params.get("divergence_required"))):
        return -1, "rsi_overbought_reversion", diagnostics
    return None, "none", diagnostics


def _signal_bias(index: int, bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], exposure: int, _holding: int) -> tuple[int | None, str, dict[str, Any]]:
    price = bars[index].close
    ma = context["bias_ma"][index]
    std = context["bias_std"][index]
    measure = str(variant.params.get("deviation_measure") or "pct_from_ma")
    deviation = None
    if price is not None and ma not in (None, 0):
        deviation = (price / ma - 1) * 100 if measure == "pct_from_ma" else ((price - ma) / std if std not in (None, 0) else None)
    diagnostics = {"bias_ma": ma, "bias_std": std, "bias_deviation": deviation, "deviation_measure": measure}
    if deviation is None:
        return None, "insufficient_history", diagnostics
    entry = _float_param(variant.params, "entry_deviation_threshold", 2.0)
    exit_threshold = _float_param(variant.params, "exit_deviation_threshold", 0.5)
    if exposure and abs(deviation) <= exit_threshold:
        return 0, "bias_exit", diagnostics
    if _trend_filter_blocks(index, price, context.get("bias_ma"), variant.params):
        return None, "trend_filter_block", diagnostics
    if deviation <= -entry:
        return 1, "bias_negative_reversion", diagnostics
    if deviation >= entry:
        return -1, "bias_positive_reversion", diagnostics
    return None, "none", diagnostics


def _signal_vwap(index: int, bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], exposure: int, _holding: int) -> tuple[int | None, str, dict[str, Any]]:
    bar = bars[index]
    price = bar.close
    vwap = context["session_vwap"][index]
    std = context["vwap_std"][index]
    spread_limit = _float_param(variant.params, "maximum_spread_bps", 9999)
    deviation_bps = None if price is None or vwap in (None, 0) else (price / vwap - 1) * 10000
    zscore = None if price is None or vwap is None or std in (None, 0) else (price - vwap) / std
    diagnostics = {"session_vwap": vwap, "vwap_deviation_bps": deviation_bps, "vwap_zscore": zscore, "spread_bps": bar.spread_bps}
    if price is None or vwap is None or deviation_bps is None or zscore is None:
        return None, "insufficient_history", diagnostics
    local_time = bar.available_time.astimezone(ET).time()
    if local_time < time(10, 0) or local_time > time(15, 30):
        return None, "time_gate", diagnostics
    if bar.spread_bps is not None and bar.spread_bps > spread_limit:
        return None, "spread_gate", diagnostics
    exit_z = _float_param(variant.params, "exit_zscore", 0.5)
    if exposure and abs(zscore) <= exit_z:
        return 0, "vwap_exit", diagnostics
    entry_bps = _float_param(variant.params, "deviation_bps", 50)
    entry_z = _float_param(variant.params, "entry_zscore", 1.5)
    if deviation_bps <= -entry_bps and zscore <= -entry_z:
        return 1, "vwap_lower_reversion", diagnostics
    if deviation_bps >= entry_bps and zscore >= entry_z:
        return -1, "vwap_upper_reversion", diagnostics
    return None, "none", diagnostics


def _signal_range_breakout(index: int, bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], _exposure: int, _holding: int) -> tuple[int | None, str, dict[str, Any]]:
    close = bars[index].close
    high = context["range_high"][index]
    low = context["range_low"][index]
    atr = context["atr"][index]
    avg_volume = context["avg_volume"][index]
    width_atr = None if high is None or low is None or atr in (None, 0) else (high - low) / atr
    diagnostics = {"range_high": high, "range_low": low, "atr": atr, "range_width_atr": width_atr, "volume_ratio": None if avg_volume in (None, 0) or bars[index].volume is None else bars[index].volume / avg_volume}
    if close is None or high is None or low is None or atr in (None, 0) or width_atr is None:
        return None, "insufficient_history", diagnostics
    if width_atr > _float_param(variant.params, "range_width_max_atr", 1.5):
        return None, "range_too_wide", diagnostics
    if diagnostics["volume_ratio"] is not None and diagnostics["volume_ratio"] < _float_param(variant.params, "volume_confirmation_ratio", 1.0):
        return None, "volume_gate", diagnostics
    buffer = _float_param(variant.params, "breakout_buffer_atr", 0.0) * atr
    if close > high + buffer:
        return 1, "range_upper_break", diagnostics
    if close < low - buffer:
        return -1, "range_lower_break", diagnostics
    return None, "none", diagnostics


def _signal_opening_range(index: int, bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], exposure: int, _holding: int) -> tuple[int | None, str, dict[str, Any]]:
    bar = bars[index]
    close = bar.close
    high = context["opening_high"].get((bar.target_candidate_id, bar.available_time.date(), _int_param(variant.params, "opening_range_minutes", 15)))
    low = context["opening_low"].get((bar.target_candidate_id, bar.available_time.date(), _int_param(variant.params, "opening_range_minutes", 15)))
    avg_vol = context["opening_avg_volume"].get((bar.target_candidate_id, bar.available_time.date(), _int_param(variant.params, "opening_range_minutes", 15)))
    diagnostics = {"opening_range_high": high, "opening_range_low": low, "opening_volume_ratio": None if avg_vol in (None, 0) or bar.volume is None else bar.volume / avg_vol}
    local_time = bar.available_time.astimezone(ET).time()
    if local_time < time(9, 30) or local_time > time(11, 0):
        return None, "time_gate", diagnostics
    first_trade = _regular_session_time_after_minutes(_int_param(variant.params, "opening_range_minutes", 15) + 5)
    if local_time < first_trade or high is None or low is None or close is None:
        return None, "opening_range_building", diagnostics
    if exposure:
        return None, "max_one_trade_context", diagnostics
    if diagnostics["opening_volume_ratio"] is not None and diagnostics["opening_volume_ratio"] < _float_param(variant.params, "volume_confirmation_ratio", 1.0):
        return None, "volume_gate", diagnostics
    buffer = _float_param(variant.params, "breakout_buffer_bps", 0.0) / 10000
    if close > high * (1 + buffer):
        return 1, "opening_range_upper_break", diagnostics
    if close < low * (1 - buffer):
        return -1, "opening_range_lower_break", diagnostics
    return None, "none", diagnostics


def _signal_volatility_breakout(index: int, bars: Sequence[Bar], variant: StrategyVariant, context: Mapping[str, Any], _exposure: int, _holding: int) -> tuple[int | None, str, dict[str, Any]]:
    vol = context["volatility"][index]
    avg = context["volatility_avg"][index]
    threshold = context["volatility_threshold"]
    close = bars[index].close
    prev = bars[index - 1].close if index > 0 else None
    diagnostics = {"volatility": vol, "volatility_avg": avg, "volatility_expansion_ratio": None if avg in (None, 0) or vol is None else vol / avg, "stop_atr_multiple": _float_param(variant.params, "stop_atr_multiple", 0.0)}
    if vol is None or avg in (None, 0) or close is None or prev is None:
        return None, "insufficient_history", diagnostics
    if vol / avg < threshold:
        return None, "no_volatility_expansion", diagnostics
    direction_filter = str(variant.params.get("direction_filter") or "none")
    if direction_filter == "trend":
        ma = context["trend_ma"][index]
        if ma is None:
            return None, "trend_missing", diagnostics
        return (1 if close > ma else -1), "volatility_trend_break", diagnostics
    if direction_filter == "range_break":
        high = context["range_high"][index]
        low = context["range_low"][index]
        if high is not None and close > high:
            return 1, "volatility_range_upper_break", diagnostics
        if low is not None and close < low:
            return -1, "volatility_range_lower_break", diagnostics
        return None, "range_break_missing", diagnostics
    return (1 if close > prev else -1), "volatility_directional_expansion", diagnostics


# ---- Parsing helpers -----------------------------------------------------


def _candidate_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    candidates: dict[str, str] = {}
    for row in rows:
        target_candidate_id = str(row.get("target_candidate_id") or row.get("candidate_id") or "").strip()
        symbol = str(row.get("symbol") or row.get("routing_symbol") or "").strip().upper()
        if target_candidate_id and symbol:
            candidates[symbol] = target_candidate_id
    return candidates


def _variant(row: Mapping[str, Any]) -> StrategyVariant:
    family = str(row.get("3_strategy_family") or row.get("strategy_family") or "").strip()
    if family not in SUPPORTED_FAMILIES:
        raise StrategySelectionError(f"unsupported or missing strategy_family: {family!r}")
    variant_id = str(row.get("3_strategy_variant") or row.get("strategy_variant") or row.get("variant_id") or "").strip()
    if not variant_id:
        raise StrategySelectionError("strategy_variant is required")
    params: dict[str, Any] = {}
    for key in ("fixed_parameters", "variable_parameters", "params", "variant_params"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            params.update(json.loads(value))
        elif isinstance(value, Mapping):
            params.update(dict(value))
    for key, value in row.items():
        if key not in {"3_strategy_family", "strategy_family", "3_strategy_variant", "strategy_variant", "variant_id", "fixed_parameters", "variable_parameters", "params", "variant_params"}:
            params.setdefault(key, value)
    return StrategyVariant(
        strategy_family=family,
        strategy_variant=variant_id,
        variant_spec_ref=str(row.get("variant_spec_ref") or row.get("strategy_spec_hash") or row.get("spec_ref") or variant_id).strip(),
        params=params,
    )


def _profile(params: Mapping[str, Any], key: str, *, min_values: int) -> tuple[Any, ...]:
    value = params.get(key)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            value = json.loads(text)
        elif text in PROFILE_VALUES.get(key, {}):
            value = PROFILE_VALUES[key][text]
    if isinstance(value, (list, tuple)) and len(value) >= min_values:
        return tuple(value)
    raise StrategySelectionError(f"{key} must be a tuple/list with at least {min_values} values")


def _volatility_profile(params: Mapping[str, Any]) -> tuple[Any, Any, int, float]:
    value = _profile(params, "volatility_profile", min_values=4)
    return value[0], value[1], int(value[2]), float(value[3])


def _threshold_pair(params: Mapping[str, Any]) -> tuple[float, float]:
    value = params.get("threshold_pair") or (30, 70)
    if isinstance(value, str):
        value = json.loads(value) if value.startswith("[") else tuple(float(part) for part in value.strip("()").split(","))
    return float(value[0]), float(value[1])


# ---- Indicator helpers ---------------------------------------------------


def _moving_average_series(values: Sequence[float | None], window: int, ma_type: str) -> list[float | None]:
    if window <= 0:
        raise StrategySelectionError("moving-average windows must be positive")
    if ma_type == "sma":
        return [_sma(values, index, window) for index in range(len(values))]
    return _ema_series(values, window)


def _sma(values: Sequence[float | None], index: int, window: int) -> float | None:
    if index + 1 < window:
        return None
    items = values[index - window + 1 : index + 1]
    if any(value is None for value in items):
        return None
    return sum(float(value) for value in items) / window


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


def _rolling_std(values: Sequence[float | None], window: int) -> list[float | None]:
    output: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            output.append(None)
            continue
        items = [value for value in values[index - window + 1 : index + 1] if value is not None]
        output.append(pstdev(items) if len(items) == window and len(set(items)) > 1 else (0.0 if len(items) == window else None))
    return output


def _rolling_high(values: Sequence[float | None], window: int, *, exclude_current: bool) -> list[float | None]:
    return [_rolling_extreme(values, index, window, max, exclude_current=exclude_current) for index in range(len(values))]


def _rolling_low(values: Sequence[float | None], window: int, *, exclude_current: bool) -> list[float | None]:
    return [_rolling_extreme(values, index, window, min, exclude_current=exclude_current) for index in range(len(values))]


def _rolling_extreme(values: Sequence[float | None], index: int, window: int, fn: Any, *, exclude_current: bool) -> float | None:
    end = index if exclude_current else index + 1
    start = end - window
    if start < 0:
        return None
    items = [value for value in values[start:end] if value is not None]
    return fn(items) if len(items) == window else None


def _atr_series(highs: Sequence[float | None], lows: Sequence[float | None], closes: Sequence[float | None], window: int) -> list[float | None]:
    tr: list[float | None] = []
    prev_close: float | None = None
    for high, low, close in zip(highs, lows, closes, strict=True):
        if high is None or low is None:
            tr.append(None)
        else:
            values = [high - low]
            if prev_close is not None:
                values.extend([abs(high - prev_close), abs(low - prev_close)])
            tr.append(max(values))
        if close is not None:
            prev_close = close
    return _moving_average_series(tr, window, "sma")


def _rsi_series(values: Sequence[float | None], period: int) -> list[float | None]:
    output: list[float | None] = [None]
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(values)):
        if values[index] is None or values[index - 1] is None:
            gains.append(0.0)
            losses.append(0.0)
        else:
            change = float(values[index]) - float(values[index - 1])
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))
        if len(gains) < period:
            output.append(None)
            continue
        avg_gain = mean(gains[-period:])
        avg_loss = mean(losses[-period:])
        if avg_loss == 0:
            output.append(100.0 if avg_gain > 0 else 50.0)
        else:
            rs = avg_gain / avg_loss
            output.append(100 - 100 / (1 + rs))
    return output


def _session_vwap(bars: Sequence[Bar]) -> list[float | None]:
    sums: dict[tuple[str, Any], tuple[float, float]] = {}
    output: list[float | None] = []
    for bar in bars:
        key = (bar.target_candidate_id, bar.available_time.astimezone(ET).date())
        price = bar.bar_vwap or bar.close
        volume = bar.volume
        if price is None or volume in (None, 0):
            output.append(None)
            continue
        pv, vol = sums.get(key, (0.0, 0.0))
        pv += price * volume
        vol += volume
        sums[key] = (pv, vol)
        output.append(pv / vol if vol else None)
    return output


def _opening_range_context(bars: Sequence[Bar]) -> dict[str, Any]:
    highs: dict[tuple[str, Any, int], float] = {}
    lows: dict[tuple[str, Any, int], float] = {}
    volumes: dict[tuple[str, Any, int], list[float]] = {}
    durations = (5, 15, 30, 60)
    for bar in bars:
        local = bar.available_time.astimezone(ET)
        minutes = (local.hour * 60 + local.minute) - (9 * 60 + 30)
        if minutes < 0:
            continue
        for duration in durations:
            if minutes < duration:
                key = (bar.target_candidate_id, local.date(), duration)
                if bar.high is not None:
                    highs[key] = max(highs.get(key, bar.high), bar.high)
                if bar.low is not None:
                    lows[key] = min(lows.get(key, bar.low), bar.low)
                if bar.volume is not None:
                    volumes.setdefault(key, []).append(bar.volume)
    return {"opening_high": highs, "opening_low": lows, "opening_avg_volume": {key: mean(value) for key, value in volumes.items() if value}}


def _returns(values: Sequence[float | None]) -> list[float | None]:
    output: list[float | None] = [None]
    for current, previous in zip(values[1:], values[:-1], strict=True):
        output.append(_safe_return(current, previous))
    return output


# ---- Small utilities -----------------------------------------------------


def _price(bar: Bar, price_field: str) -> float | None:
    if price_field == "bar_hlc3":
        if bar.high is None or bar.low is None or bar.close is None:
            return None
        return (bar.high + bar.low + bar.close) / 3
    return bar.close


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise StrategySelectionError("timestamp is required")
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


def _delta(first: float | None, second: float | None) -> float | None:
    if first is None or second is None:
        return None
    return first - second


def _normalized_slope(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return current / previous - 1


def _confirmed_cross(index: int, fast: Sequence[float | None], slow: Sequence[float | None], confirmation: int, min_slope: float) -> int | None:
    if index < confirmation:
        return None
    deltas = [_delta(fast[pos], slow[pos]) for pos in range(index - confirmation + 1, index + 1)]
    previous_delta = _delta(fast[index - confirmation], slow[index - confirmation])
    if previous_delta is None or any(delta is None for delta in deltas):
        return None
    slope = _normalized_slope(fast[index], fast[index - 1])
    if slope is None or abs(slope) < min_slope:
        return None
    if previous_delta <= 0 and all(float(delta) > 0 for delta in deltas):
        return 1
    if previous_delta >= 0 and all(float(delta) < 0 for delta in deltas):
        return -1
    return None


def _trend_filter_blocks(index: int, price: float | None, series: Any, params: Mapping[str, Any]) -> bool:
    if not params.get("trend_filter_enabled") or price is None or not isinstance(series, Sequence) or index < 1:
        return False
    current = series[index]
    previous = series[index - 1]
    slope = _normalized_slope(current, previous)
    if slope is None:
        return False
    return (price < current and slope < -0.001) or (price > current and slope > 0.001)


def _regular_session_time_after_minutes(minutes_after_open: int) -> time:
    total = 9 * 60 + 30 + minutes_after_open
    return time(total // 60, total % 60)


def _rsi_exit_long(rsi: float, mode: str) -> bool:
    return rsi >= 50 if mode == "50_cross" else rsi >= 45


def _rsi_exit_short(rsi: float, mode: str) -> bool:
    return rsi <= 50 if mode == "50_cross" else rsi <= 55


def _rsi_entry_allowed(index: int, bars: Sequence[Bar], context: Mapping[str, Any], *, long_side: bool, divergence: bool) -> bool:
    if not divergence:
        return True
    if index < 3 or bars[index].close is None or bars[index - 3].close is None or context["rsi"][index - 3] is None or context["rsi"][index] is None:
        return False
    price_change = float(bars[index].close) - float(bars[index - 3].close)
    rsi_change = float(context["rsi"][index]) - float(context["rsi"][index - 3])
    return (price_change < 0 and rsi_change > 0) if long_side else (price_change > 0 and rsi_change < 0)


def _int_param(params: Mapping[str, Any], key: str, default: int, *, minimum: int | None = None) -> int:
    value = int(params.get(key) if params.get(key) not in (None, "") else default)
    return max(minimum, value) if minimum is not None else value


def _float_param(params: Mapping[str, Any], key: str, default: float, *, minimum: float | None = None) -> float:
    value = float(params.get(key) if params.get(key) not in (None, "") else default)
    return max(minimum, value) if minimum is not None else value
