# equity_abnormal_activity

Derived event detector for `EventOverlayModel`.

## Boundary

- Input: saved `equity_bar.csv` and optional `equity_liquidity_bar.csv` / benchmark `equity_bar.csv` files.
- Output: final saved `equity_abnormal_activity_event.csv`.
- No live fetch. Raw Alpaca acquisition remains owned by `alpaca_bars` and `alpaca_liquidity`.

## Required params

- `bars_csv_path` — saved equity bar CSV for one symbol.

## Optional params

- `benchmark_bars_csv_path` — benchmark or sector ETF bars aligned by `timestamp_et`.
- `liquidity_csv_path` — equity liquidity bars aligned by `interval_start_et`.
- `lookback_intervals` — default `20`.
- `min_abs_return_zscore` — default `3.0`.
- `min_volume_zscore` — default `3.0`.
- `min_abs_relative_strength_zscore` — default `3.0`.
- `min_abs_gap_pct` — default `0.04`.
- `min_liquidity_spread_zscore` — default `3.0`.
- `model_standard` — default `equity_abnormal_activity_v0`.

## Output

`saved/equity_abnormal_activity_event.csv` with compact event-style rows for abnormal price, volume, relative-strength, gap, and liquidity behavior.
