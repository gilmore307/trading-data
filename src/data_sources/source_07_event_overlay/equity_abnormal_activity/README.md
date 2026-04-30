# source_07_event_overlay/equity_abnormal_activity

Derived event detector inside the `source_07_event_overlay` EventOverlayModel layer. This is not a standalone manager-facing numbered data source.

It converts saved equity/ETF bars, optional benchmark bars, and optional liquidity rows into compact `equity_abnormal_activity_event` evidence rows that Layer 07 can reference as prior signals.

## Inputs

- `params.bar_path` — required saved `equity_bar.csv` path.
- `params.benchmark_bar_path` — optional benchmark/sector ETF `equity_bar.csv` path.
- `params.liquidity_path` — optional `equity_liquidity_bar.csv` path.
- `params.config_path` — reviewed one-off config override path; normal runs use this folder's `config.json`.

## Config defaults

- `bar_grain`
- `lookback_intervals`
- return/volume/relative-strength/gap/liquidity thresholds
- `model_standard`

## Output

`saved/equity_abnormal_activity_event.csv` with compact event-style rows for abnormal price, volume, relative-strength, gap, and liquidity behavior. Full details remain in evidence/reference fields rather than in the Layer 07 event overview table.
