"""Point-in-time sector/industry behavior evidence for SecuritySelectionModel.

This module owns Model 2 rotation/leadership evidence. It consumes the same
cleaned market-regime bar source and reviewed ETF combination CSVs as the Layer
1 feature generator, but emits candidate-comparison rows keyed by snapshot time,
candidate ETF, comparison ETF, and reviewed rotation pair id. Holdings and
stock-exposure evidence are intentionally downstream of Layer 2.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Sequence

from data_feature.feature_01_market_regime import generator as market_features

ET = market_features.ET
ROTATION_COMBINATION_TYPES = market_features.MODEL2_ROTATION_COMBINATION_TYPES
METADATA_COLUMNS = {
    "snapshot_time",
    "candidate_symbol",
    "candidate_type",
    "comparison_symbol",
    "rotation_pair_id",
    "rotation_pair_type",
    "feature_bar_grain",
}

read_csv_rows = market_features.read_csv_rows
build_inputs = market_features.build_inputs
infer_snapshot_times = market_features.infer_snapshot_times
MarketRegimeInputs = market_features.MarketRegimeInputs
Combination = market_features.Combination


def rotation_combinations(inputs: MarketRegimeInputs) -> list[Combination]:
    """Return reviewed sector/industry rotation combinations for Model 2."""

    return [combo for combo in inputs.combinations if combo.combination_type in ROTATION_COMBINATION_TYPES]


def generate_rows(inputs: MarketRegimeInputs, snapshot_times: Sequence[str | datetime] | None = None) -> list[dict[str, Any]]:
    snapshots = [market_features._parse_timestamp(value) if not isinstance(value, datetime) else value.astimezone(ET) for value in (snapshot_times or infer_snapshot_times(inputs))]
    rows: list[dict[str, Any]] = []
    for snapshot_time in sorted(snapshots):
        rows.append(generate_sector_rotation_summary_row(inputs, snapshot_time))
        for combo in rotation_combinations(inputs):
            rows.append(generate_row(inputs, combo, snapshot_time))
    return rows


def generate_sector_rotation_summary_row(inputs: MarketRegimeInputs, snapshot_time: datetime) -> dict[str, Any]:
    snapshot_time = snapshot_time.astimezone(ET)
    row: dict[str, Any] = {
        "snapshot_time": snapshot_time.isoformat(),
        "candidate_symbol": "SECTOR_OBSERVATION_UNIVERSE",
        "candidate_type": "sector_rotation_summary",
        "comparison_symbol": "MARKET",
        "rotation_pair_id": "sector_observation_breadth",
        "rotation_pair_type": "sector_rotation_summary",
        "feature_bar_grain": "mixed",
    }

    daily_cache: dict[str, list[market_features.Bar]] = {}

    def daily(symbol: str) -> list[market_features.Bar]:
        key = symbol.upper()
        if key not in daily_cache:
            daily_cache[key] = market_features._daily_bars_at(inputs.bars_by_symbol.get(key, []), snapshot_time)
        return daily_cache[key]

    _add_sector_observation_breadth(row, inputs, daily)
    return row


def generate_row(inputs: MarketRegimeInputs, combo: Combination, snapshot_time: datetime) -> dict[str, Any]:
    snapshot_time = snapshot_time.astimezone(ET)
    row: dict[str, Any] = {
        "snapshot_time": snapshot_time.isoformat(),
        "candidate_symbol": combo.numerator_symbol,
        "candidate_type": "sector_industry_etf",
        "comparison_symbol": combo.denominator_symbol,
        "rotation_pair_id": combo.combination_id,
        "rotation_pair_type": combo.combination_type,
        "feature_bar_grain": combo.feature_bar_grain,
    }

    daily_cache: dict[str, list[market_features.Bar]] = {}
    close_cache: dict[tuple[str, datetime], float | None] = {}

    def daily(symbol: str) -> list[market_features.Bar]:
        key = symbol.upper()
        if key not in daily_cache:
            daily_cache[key] = market_features._daily_bars_at(inputs.bars_by_symbol.get(key, []), snapshot_time)
        return daily_cache[key]

    def close_at(symbol: str, at: datetime) -> float | None:
        cache_key = (symbol.upper(), at)
        if cache_key not in close_cache:
            close_cache[cache_key] = market_features._latest_close_at(inputs.bars_by_symbol.get(symbol.upper(), []), at)
        return close_cache[cache_key]

    _add_relative_strength_return(row, combo, close_at, daily, snapshot_time)
    _add_relative_strength_volatility(row, combo, daily)
    _add_relative_strength_trend(row, combo, daily)
    _add_relative_strength_correlation(row, combo, daily)
    return row


def _add_relative_strength_return(row: dict[str, Any], combo: Combination, close_at: Any, daily: Any, snapshot_time: datetime) -> None:
    if combo.feature_bar_grain == "30m":
        current = market_features._safe_div(close_at(combo.numerator_symbol, snapshot_time), close_at(combo.denominator_symbol, snapshot_time))
        previous = market_features._safe_div(close_at(combo.numerator_symbol, snapshot_time - timedelta(minutes=30)), close_at(combo.denominator_symbol, snapshot_time - timedelta(minutes=30)))
        value = market_features._safe_log_ratio(current, previous)
        row["relative_strength_return_30m"] = value
    else:
        numerator = market_features._daily_close_series(daily(combo.numerator_symbol))
        denominator = market_features._daily_close_series(daily(combo.denominator_symbol))
        ratio = market_features._ratio_series(numerator, denominator)
        value = market_features._safe_log_ratio(ratio[-1], ratio[-2]) if len(ratio) >= 2 else None
        row["relative_strength_return_1d"] = value
    row["relative_strength_return"] = value


def _add_relative_strength_volatility(row: dict[str, Any], combo: Combination, daily: Any) -> None:
    numerator_vol = market_features._rolling_realized_vol(market_features._daily_log_returns(daily(combo.numerator_symbol)), 20)
    denominator_vol = market_features._rolling_realized_vol(market_features._daily_log_returns(daily(combo.denominator_symbol)), 20)
    row["relative_strength_realized_vol_20d_ratio"] = market_features._safe_div(numerator_vol, denominator_vol)


def _add_relative_strength_trend(row: dict[str, Any], combo: Combination, daily: Any) -> None:
    ratio = market_features._ratio_series(
        market_features._daily_close_series(daily(combo.numerator_symbol)),
        market_features._daily_close_series(daily(combo.denominator_symbol)),
    )
    market_features._add_ma_feature_set(row, "relative_strength", ratio, include_ma_values=False)


def _add_relative_strength_correlation(row: dict[str, Any], combo: Combination, daily: Any) -> None:
    numerator_returns = market_features._daily_log_returns(daily(combo.numerator_symbol))
    denominator_returns = market_features._daily_log_returns(daily(combo.denominator_symbol))
    corr20 = market_features._sample_corr(numerator_returns, denominator_returns, 20)
    corr60 = market_features._sample_corr(numerator_returns, denominator_returns, 60)
    row["relative_strength_return_corr_20d"] = corr20
    row["relative_strength_return_corr_60d"] = corr60
    row["relative_strength_return_corr_20d_60d_change"] = None if corr20 is None or corr60 is None else corr20 - corr60


def payload_columns(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    columns = {key for row in rows for key in row if key not in METADATA_COLUMNS}
    return sorted(columns)


def candidate_parameter_inputs(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return numeric payload fields intended for later Model 2 parameterization."""

    return {key: value for key, value in row.items() if key not in METADATA_COLUMNS}


def relative_strength_signal_average(row: Mapping[str, Any]) -> float | None:
    """Small diagnostic reducer used by tests and local inspection only."""

    values = [market_features._safe_float(row.get(key)) for key in ("relative_strength_return", "relative_strength_distance_to_ma20", "relative_strength_ma_alignment_score")]
    clean = [value for value in values if value is not None]
    return mean(clean) if clean else None


def _add_sector_observation_breadth(row: dict[str, Any], inputs: MarketRegimeInputs, daily: Any) -> None:
    returns1: list[float] = []
    returns5: list[float] = []
    above20 = above50 = above200 = 0
    above20_count = above50_count = above200_count = 0
    distance20: list[float] = []
    returns20: list[float] = []

    for symbol in inputs.sector_observation_symbols:
        bars = daily(symbol)
        closes = market_features._daily_close_series(bars)
        r1 = market_features._log_return_from_daily_bars(bars, 1)
        r5 = market_features._log_return_from_daily_bars(bars, 5)
        r20 = market_features._log_return_from_daily_bars(bars, 20)
        if r1 is not None:
            returns1.append(r1)
        if r5 is not None:
            returns5.append(r5)
        if r20 is not None:
            returns20.append(r20)
        current = closes[-1] if closes else None
        for window in market_features.MA_WINDOWS:
            ma = market_features._moving_average(closes, window)
            if current is not None and ma is not None:
                if window == 20:
                    above20_count += 1
                    above20 += 1 if current > ma else 0
                    distance20.append(current / ma - 1)
                elif window == 50:
                    above50_count += 1
                    above50 += 1 if current > ma else 0
                elif window == 200:
                    above200_count += 1
                    above200 += 1 if current > ma else 0

    row["sector_observation_positive_return_1d_pct"] = _positive_pct(returns1)
    row["sector_observation_positive_return_5d_pct"] = _positive_pct(returns5)
    row["sector_observation_above_ma20_pct"] = market_features._safe_div(above20, above20_count)
    row["sector_observation_above_ma50_pct"] = market_features._safe_div(above50, above50_count)
    row["sector_observation_above_ma200_pct"] = market_features._safe_div(above200, above200_count)
    row["sector_observation_distance_to_ma20_avg"] = mean(distance20) if distance20 else None
    row["sector_observation_distance_to_ma20_dispersion"] = pstdev(distance20) if len(distance20) >= 2 else None
    row["sector_observation_return_20d_dispersion"] = pstdev(returns20) if len(returns20) >= 2 else None


def _positive_pct(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value > 0) / len(values)
