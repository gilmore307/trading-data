# 06_event_overlay_model_inputs/equity_abnormal_activity

Derived event detector inside the `06_event_overlay_model_inputs` EventOverlayModel layer. This is not a standalone manager-facing data bundle.

## Boundary

- Input: saved `equity_bar.csv` and optional `equity_liquidity_bar.csv` / benchmark `equity_bar.csv` files.
- Output: final saved `equity_abnormal_activity_event.csv`.
- No live fetch. Raw Alpaca acquisition remains owned by `alpaca_bars` and `alpaca_liquidity`.

## Required params

- `bars_csv_path` — saved equity bar CSV for one symbol.

## Bundle config

`config.json` lives in this bundle folder and owns reusable detector defaults such as bar grain, lookback, thresholds, and `model_standard`. Task keys may override run-specific values.

## Optional params

- `benchmark_bars_csv_path` — benchmark or sector ETF bars aligned by `timestamp`.
- `config_path` — reviewed one-off config override path; normal runs use bundle-local `config.json`.
- `liquidity_csv_path` — equity liquidity bars aligned by `interval_start`.
- `lookback_intervals` — default `20`.
- `min_abs_return_zscore` — default `3.0`.
- `min_volume_zscore` — default `3.0`.
- `min_abs_relative_strength_zscore` — default `3.0`.
- `min_abs_gap_pct` — default `0.04`.
- `min_liquidity_spread_zscore` — default `3.0`.
- `model_standard` — default `equity_abnormal_activity_v0`.

## Output

`saved/equity_abnormal_activity_event.csv` with compact event-style rows for abnormal price, volume, relative-strength, gap, and liquidity behavior.
