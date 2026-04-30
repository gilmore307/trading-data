"""Point-in-time generator for the ``feature_01_market_regime`` wide table.

The generator consumes cleaned ``source_01_market_regime`` bar rows plus the reviewed
market-regime ETF universe and relative-strength combination CSVs. It performs no
provider calls and no database writes; the SQL script wrapper under ``scripts/`` owns
runtime reads/writes.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MARKET_STATE_TYPE = "market_state_etf"
SECTOR_OBSERVATION_TYPE = "sector_observation_etf"
RETURN_LOOKBACKS = ("30m", "1d", "5d", "20d")
REALIZED_VOL_LOOKBACKS = (5, 20, 60)
MA_WINDOWS = (20, 50, 200)
LAMBDA_EWMA = 0.94


def _lower_symbol(symbol: str) -> str:
    return str(symbol).strip().lower()


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _safe_log_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or numerator <= 0 or denominator <= 0:
        return None
    return math.log(numerator / denominator)


def _sign(value: float | None) -> int | None:
    if value is None:
        return None
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _parse_timestamp(value: Any) -> datetime:
    text = str(value).strip()
    if not text:
        raise ValueError("timestamp is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET)


def _is_daily_timeframe(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1d", "1day", "day", "daily", "1day"}


def _daily_available_time(timestamp: datetime) -> datetime:
    return datetime.combine(timestamp.astimezone(ET).date(), time(16, 0), tzinfo=ET)


@dataclass(frozen=True)
class Bar:
    symbol: str
    timeframe: str
    timestamp: datetime
    available_time: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None


@dataclass(frozen=True)
class Combination:
    combination_id: str
    numerator_symbol: str
    denominator_symbol: str
    feature_bar_grain: str


@dataclass(frozen=True)
class MarketRegimeInputs:
    bars_by_symbol: dict[str, list[Bar]]
    market_state_symbols: list[str]
    sector_observation_symbols: list[str]
    combinations: list[Combination]


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [{str(k): str(v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def build_inputs(
    *,
    bar_rows: Iterable[Mapping[str, Any]],
    universe_rows: Iterable[Mapping[str, Any]],
    combination_rows: Iterable[Mapping[str, Any]],
) -> MarketRegimeInputs:
    market_state_symbols: list[str] = []
    sector_observation_symbols: list[str] = []
    for row in universe_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        universe_type = str(row.get("universe_type") or "").strip()
        if not symbol:
            continue
        if universe_type == MARKET_STATE_TYPE:
            market_state_symbols.append(symbol)
        elif universe_type == SECTOR_OBSERVATION_TYPE:
            sector_observation_symbols.append(symbol)

    combinations: list[Combination] = []
    for row in combination_rows:
        combination_id = str(row.get("combination_id") or "").strip().lower()
        numerator = str(row.get("numerator_symbol") or "").strip().upper()
        denominator = str(row.get("denominator_symbol") or "").strip().upper()
        if combination_id and numerator and denominator:
            combinations.append(Combination(combination_id, numerator, denominator, str(row.get("feature_bar_grain") or "").strip().lower()))

    bars_by_symbol: dict[str, list[Bar]] = {}
    for row in bar_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        timestamp = _parse_timestamp(row.get("timestamp"))
        timeframe = str(row.get("timeframe") or "").strip()
        available_time = _daily_available_time(timestamp) if _is_daily_timeframe(timeframe) else timestamp
        bar = Bar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            available_time=available_time,
            open=_safe_float(row.get("bar_open")),
            high=_safe_float(row.get("bar_high")),
            low=_safe_float(row.get("bar_low")),
            close=_safe_float(row.get("bar_close")),
            volume=_safe_float(row.get("bar_volume")),
        )
        bars_by_symbol.setdefault(symbol, []).append(bar)

    for symbol, bars in bars_by_symbol.items():
        bars_by_symbol[symbol] = sorted(bars, key=lambda item: (item.available_time, item.timestamp))

    return MarketRegimeInputs(
        bars_by_symbol=bars_by_symbol,
        market_state_symbols=sorted(set(market_state_symbols)),
        sector_observation_symbols=sorted(set(sector_observation_symbols)),
        combinations=sorted(combinations, key=lambda item: item.combination_id),
    )


def infer_snapshot_times(inputs: MarketRegimeInputs, *, anchor_symbol: str = "SPY") -> list[datetime]:
    bars = inputs.bars_by_symbol.get(anchor_symbol.upper(), [])
    times = {bar.available_time for bar in bars if not _is_daily_timeframe(bar.timeframe) and _is_30_minute_snapshot_time(bar.available_time)}
    return sorted(times)


def _is_30_minute_snapshot_time(value: datetime) -> bool:
    et_value = value.astimezone(ET)
    regular_open = time(9, 30)
    regular_close = time(16, 0)
    local_time = et_value.time()
    if local_time <= regular_open or local_time > regular_close:
        return False
    return et_value.second == 0 and et_value.microsecond == 0 and et_value.minute in {0, 30}


def generate_rows(inputs: MarketRegimeInputs, snapshot_times: Sequence[str | datetime] | None = None) -> list[dict[str, Any]]:
    snapshots = [_parse_timestamp(value) if not isinstance(value, datetime) else value.astimezone(ET) for value in (snapshot_times or infer_snapshot_times(inputs))]
    return [generate_row(inputs, snapshot_time) for snapshot_time in sorted(snapshots)]


def generate_row(inputs: MarketRegimeInputs, snapshot_time: datetime) -> dict[str, Any]:
    snapshot_time = snapshot_time.astimezone(ET)
    row: dict[str, Any] = {"snapshot_time": snapshot_time.isoformat()}

    daily_cache: dict[str, list[Bar]] = {}
    close_cache: dict[tuple[str, datetime], float | None] = {}

    def daily(symbol: str) -> list[Bar]:
        key = symbol.upper()
        if key not in daily_cache:
            daily_cache[key] = _daily_bars_at(inputs.bars_by_symbol.get(key, []), snapshot_time)
        return daily_cache[key]

    def close_at(symbol: str, at: datetime) -> float | None:
        cache_key = (symbol.upper(), at)
        if cache_key not in close_cache:
            close_cache[cache_key] = _latest_close_at(inputs.bars_by_symbol.get(symbol.upper(), []), at)
        return close_cache[cache_key]

    for symbol in inputs.market_state_symbols:
        subject = _lower_symbol(symbol)
        _add_return_features(row, subject, close_at, symbol, snapshot_time, daily(symbol))
        _add_volatility_features(row, subject, daily(symbol))
        _add_single_symbol_ma_features(row, subject, daily(symbol))

    _add_relative_strength_features(row, inputs, close_at, daily, snapshot_time)
    _add_cross_asset_volatility_ratios(row, inputs, daily)
    _add_ratio_ma_features(row, inputs, daily)
    _add_correlation_features(row, inputs, daily)
    _add_market_state_correlation_concentration(row, inputs, daily)
    _add_sector_observation_breadth(row, inputs, daily)
    return row


def _daily_bars_at(bars: Sequence[Bar], snapshot_time: datetime) -> list[Bar]:
    return [bar for bar in bars if _is_daily_timeframe(bar.timeframe) and bar.available_time <= snapshot_time and bar.close is not None]


def _latest_close_at(bars: Sequence[Bar], at: datetime) -> float | None:
    latest: Bar | None = None
    for bar in bars:
        if bar.available_time <= at and bar.close is not None:
            latest = bar
        elif bar.available_time > at:
            break
    return None if latest is None else latest.close


def _daily_close_series(bars: Sequence[Bar]) -> list[float]:
    return [bar.close for bar in bars if bar.close is not None]


def _daily_log_returns(bars: Sequence[Bar]) -> list[float]:
    closes = _daily_close_series(bars)
    returns: list[float] = []
    for previous, current in zip(closes, closes[1:]):
        value = _safe_log_ratio(current, previous)
        if value is not None:
            returns.append(value)
    return returns


def _log_return_from_daily_bars(bars: Sequence[Bar], periods: int) -> float | None:
    closes = _daily_close_series(bars)
    if len(closes) <= periods:
        return None
    return _safe_log_ratio(closes[-1], closes[-periods - 1])


def _std(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    return pstdev(values)


def _sample_corr(left: Sequence[float], right: Sequence[float], window: int) -> float | None:
    pairs = [(a, b) for a, b in zip(left[-window:], right[-window:]) if a is not None and b is not None]
    if len(pairs) < 2:
        return None
    xs = [item[0] for item in pairs]
    ys = [item[1] for item in pairs]
    mean_x = mean(xs)
    mean_y = mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    return cov / math.sqrt(var_x * var_y)


def _rolling_realized_vol(log_returns: Sequence[float], window: int) -> float | None:
    if len(log_returns) < window:
        return None
    std = _std(log_returns[-window:])
    return None if std is None else std * math.sqrt(252)


def _moving_average(values: Sequence[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _ratio_series(numerator: Sequence[float], denominator: Sequence[float]) -> list[float]:
    size = min(len(numerator), len(denominator))
    output: list[float] = []
    for num, den in zip(numerator[-size:], denominator[-size:]):
        value = _safe_div(num, den)
        if value is not None and value > 0:
            output.append(value)
    return output


def _add_return_features(row: dict[str, Any], subject: str, close_at: Any, symbol: str, snapshot_time: datetime, daily_bars: Sequence[Bar]) -> None:
    row[f"{subject}_return_30m"] = _safe_log_ratio(close_at(symbol, snapshot_time), close_at(symbol, snapshot_time - timedelta(minutes=30)))
    for lookback, periods in {"1d": 1, "5d": 5, "20d": 20}.items():
        row[f"{subject}_return_{lookback}"] = _log_return_from_daily_bars(daily_bars, periods)


def _add_relative_strength_features(row: dict[str, Any], inputs: MarketRegimeInputs, close_at: Any, daily: Any, snapshot_time: datetime) -> None:
    for combo in inputs.combinations:
        if combo.feature_bar_grain == "30m":
            current = _safe_div(close_at(combo.numerator_symbol, snapshot_time), close_at(combo.denominator_symbol, snapshot_time))
            previous = _safe_div(close_at(combo.numerator_symbol, snapshot_time - timedelta(minutes=30)), close_at(combo.denominator_symbol, snapshot_time - timedelta(minutes=30)))
            row[f"{combo.combination_id}_30m"] = _safe_log_ratio(current, previous)
        else:
            numerator = _daily_close_series(daily(combo.numerator_symbol))
            denominator = _daily_close_series(daily(combo.denominator_symbol))
            ratio = _ratio_series(numerator, denominator)
            row[f"{combo.combination_id}_1d"] = _safe_log_ratio(ratio[-1], ratio[-2]) if len(ratio) >= 2 else None


def _add_volatility_features(row: dict[str, Any], subject: str, daily_bars: Sequence[Bar]) -> None:
    log_returns = _daily_log_returns(daily_bars)
    vols = {window: _rolling_realized_vol(log_returns, window) for window in REALIZED_VOL_LOOKBACKS}
    for window, value in vols.items():
        row[f"{subject}_realized_vol_{window}d"] = value
    row[f"{subject}_realized_vol_5d_20d_ratio"] = _safe_div(vols[5], vols[20])
    row[f"{subject}_realized_vol_20d_60d_ratio"] = _safe_div(vols[20], vols[60])
    row[f"{subject}_ewma_vol"] = _ewma_vol(log_returns)
    row[f"{subject}_atr_pct_14d"] = _atr_pct(daily_bars, 14)
    row[f"{subject}_realized_vol_20d_percentile_252d"] = _rolling_percentile(_realized_vol_history(log_returns, 20), 252)
    row[f"{subject}_realized_vol_20d_zscore_252d"] = _rolling_zscore(_realized_vol_history(log_returns, 20), 252)
    row[f"{subject}_parkinson_vol_20d"] = _parkinson_vol(daily_bars, 20)
    row[f"{subject}_garman_klass_vol_20d"] = _garman_klass_vol(daily_bars, 20)


def _realized_vol_history(log_returns: Sequence[float], window: int) -> list[float]:
    output: list[float] = []
    for end in range(window, len(log_returns) + 1):
        value = _rolling_realized_vol(log_returns[:end], window)
        if value is not None:
            output.append(value)
    return output


def _ewma_vol(log_returns: Sequence[float], lambda_: float = LAMBDA_EWMA) -> float | None:
    if not log_returns:
        return None
    variance = log_returns[0] ** 2
    for value in log_returns[1:]:
        variance = lambda_ * variance + (1 - lambda_) * value**2
    return math.sqrt(variance) * math.sqrt(252)


def _atr_pct(bars: Sequence[Bar], window: int) -> float | None:
    if len(bars) < window + 1:
        return None
    ranges: list[float] = []
    for previous, current in zip(bars[-window - 1 : -1], bars[-window:]):
        if current.high is None or current.low is None or previous.close is None:
            return None
        ranges.append(max(current.high - current.low, abs(current.high - previous.close), abs(current.low - previous.close)))
    return _safe_div(mean(ranges), bars[-1].close)


def _rolling_percentile(values: Sequence[float], window: int) -> float | None:
    if len(values) < window:
        return None
    sample = list(values[-window:])
    current = sample[-1]
    return sum(1 for value in sample if value <= current) / len(sample)


def _rolling_zscore(values: Sequence[float], window: int) -> float | None:
    if len(values) < window:
        return None
    sample = list(values[-window:])
    std = _std(sample)
    if std in (None, 0):
        return None
    return (sample[-1] - mean(sample)) / std


def _parkinson_vol(bars: Sequence[Bar], window: int) -> float | None:
    if len(bars) < window:
        return None
    terms: list[float] = []
    for bar in bars[-window:]:
        value = _safe_log_ratio(bar.high, bar.low)
        if value is None:
            return None
        terms.append(value**2)
    return math.sqrt(sum(terms) / (4 * window * math.log(2))) * math.sqrt(252)


def _garman_klass_vol(bars: Sequence[Bar], window: int) -> float | None:
    if len(bars) < window:
        return None
    terms: list[float] = []
    for bar in bars[-window:]:
        high_low = _safe_log_ratio(bar.high, bar.low)
        close_open = _safe_log_ratio(bar.close, bar.open)
        if high_low is None or close_open is None:
            return None
        terms.append(0.5 * high_low**2 - (2 * math.log(2) - 1) * close_open**2)
    variance = mean(terms)
    if variance < 0:
        return None
    return math.sqrt(variance) * math.sqrt(252)


def _add_cross_asset_volatility_ratios(row: dict[str, Any], inputs: MarketRegimeInputs, daily: Any) -> None:
    vol_cache: dict[str, float | None] = {}
    for combo in inputs.combinations:
        for symbol in (combo.numerator_symbol, combo.denominator_symbol):
            vol_cache.setdefault(symbol, _rolling_realized_vol(_daily_log_returns(daily(symbol)), 20))
        row[f"{combo.combination_id}_realized_vol_20d_ratio"] = _safe_div(vol_cache[combo.numerator_symbol], vol_cache[combo.denominator_symbol])


def _add_single_symbol_ma_features(row: dict[str, Any], subject: str, daily_bars: Sequence[Bar]) -> None:
    closes = _daily_close_series(daily_bars)
    _add_ma_feature_set(row, subject, closes, include_ma_values=False)


def _add_ratio_ma_features(row: dict[str, Any], inputs: MarketRegimeInputs, daily: Any) -> None:
    for combo in inputs.combinations:
        ratio = _ratio_series(_daily_close_series(daily(combo.numerator_symbol)), _daily_close_series(daily(combo.denominator_symbol)))
        _add_ma_feature_set(row, combo.combination_id, ratio, include_ma_values=True)


def _add_ma_feature_set(row: dict[str, Any], subject: str, values: Sequence[float], *, include_ma_values: bool) -> None:
    ma = {window: _moving_average(values, window) for window in MA_WINDOWS}
    if include_ma_values:
        for window in MA_WINDOWS:
            row[f"{subject}_ma{window}"] = ma[window]
    current = values[-1] if values else None
    for window in MA_WINDOWS:
        row[f"{subject}_distance_to_ma{window}"] = None if current is None or ma[window] in (None, 0) else current / ma[window] - 1
    slopes = {20: 5, 50: 10, 200: 20}
    for window, lag in slopes.items():
        current_ma = ma[window]
        previous_ma = _moving_average(values[: -lag], window) if len(values) > lag else None
        row[f"{subject}_ma{window}_slope_{lag}d"] = None if current_ma is None or previous_ma in (None, 0) else current_ma / previous_ma - 1
    score_terms = [_sign(None if current is None or ma[20] is None else current - ma[20]), _sign(None if ma[20] is None or ma[50] is None else ma[20] - ma[50]), _sign(None if ma[50] is None or ma[200] is None else ma[50] - ma[200])]
    row[f"{subject}_ma_alignment_score"] = None if any(term is None for term in score_terms) else sum(score_terms)  # type: ignore[arg-type]
    row[f"{subject}_ma20_ma50_spread"] = None if ma[20] is None or ma[50] in (None, 0) else ma[20] / ma[50] - 1
    row[f"{subject}_ma50_ma200_spread"] = None if ma[50] is None or ma[200] in (None, 0) else ma[50] / ma[200] - 1


def _add_correlation_features(row: dict[str, Any], inputs: MarketRegimeInputs, daily: Any) -> None:
    returns_cache = {symbol: _daily_log_returns(daily(symbol)) for combo in inputs.combinations for symbol in (combo.numerator_symbol, combo.denominator_symbol)}
    for combo in inputs.combinations:
        corr20 = _sample_corr(returns_cache[combo.numerator_symbol], returns_cache[combo.denominator_symbol], 20)
        corr60 = _sample_corr(returns_cache[combo.numerator_symbol], returns_cache[combo.denominator_symbol], 60)
        row[f"{combo.combination_id}_return_corr_20d"] = corr20
        row[f"{combo.combination_id}_return_corr_60d"] = corr60
        row[f"{combo.combination_id}_return_corr_20d_60d_change"] = None if corr20 is None or corr60 is None else corr20 - corr60


def _add_market_state_correlation_concentration(row: dict[str, Any], inputs: MarketRegimeInputs, daily: Any) -> None:
    returns = {symbol: _daily_log_returns(daily(symbol)) for symbol in inputs.market_state_symbols}
    for window in (20, 60):
        correlations: list[float] = []
        for index, left in enumerate(inputs.market_state_symbols):
            for right in inputs.market_state_symbols[index + 1 :]:
                value = _sample_corr(returns[left], returns[right], window)
                if value is not None:
                    correlations.append(value)
        row[f"market_state_avg_return_corr_{window}d"] = mean(correlations) if correlations else None
        row[f"market_state_avg_abs_return_corr_{window}d"] = mean(abs(value) for value in correlations) if correlations else None
        row[f"market_state_return_corr_dispersion_{window}d"] = pstdev(correlations) if len(correlations) >= 2 else None


def _add_sector_observation_breadth(row: dict[str, Any], inputs: MarketRegimeInputs, daily: Any) -> None:
    returns1: list[float] = []
    returns5: list[float] = []
    above20 = above50 = above200 = 0
    above20_count = above50_count = above200_count = 0
    distance20: list[float] = []
    returns20: list[float] = []

    for symbol in inputs.sector_observation_symbols:
        bars = daily(symbol)
        closes = _daily_close_series(bars)
        r1 = _log_return_from_daily_bars(bars, 1)
        r5 = _log_return_from_daily_bars(bars, 5)
        r20 = _log_return_from_daily_bars(bars, 20)
        if r1 is not None:
            returns1.append(r1)
        if r5 is not None:
            returns5.append(r5)
        if r20 is not None:
            returns20.append(r20)
        current = closes[-1] if closes else None
        for window in MA_WINDOWS:
            ma = _moving_average(closes, window)
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
    row["sector_observation_above_ma20_pct"] = _safe_div(above20, above20_count)
    row["sector_observation_above_ma50_pct"] = _safe_div(above50, above50_count)
    row["sector_observation_above_ma200_pct"] = _safe_div(above200, above200_count)
    row["sector_observation_distance_to_ma20_avg"] = mean(distance20) if distance20 else None
    row["sector_observation_distance_to_ma20_dispersion"] = pstdev(distance20) if len(distance20) >= 2 else None
    row["sector_observation_return_20d_dispersion"] = pstdev(returns20) if len(returns20) >= 2 else None


def _positive_pct(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value > 0) / len(values)
