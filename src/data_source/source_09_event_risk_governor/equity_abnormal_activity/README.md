# source_09_event_risk_governor/equity_abnormal_activity

Derived event detector inside the `source_09_event_risk_governor` Layer 9 EventRiskGovernor surface. This is not a standalone manager-facing numbered data source.

It converts saved equity/ETF bars, optional benchmark bars, and optional liquidity rows into compact `equity_abnormal_activity_event` evidence rows inside the Layer 9 event-risk evidence surface. Layer 4 may consume only reviewed/promoted evidence packets, not raw abnormal-activity rows.

## Inputs

- `params.bar_path` — required saved `equity_bar.csv` path.
- `params.benchmark_bar_path` — optional benchmark/sector ETF `equity_bar.csv` path.
- `params.liquidity_path` — optional `equity_liquidity_bar.csv` path.
- `params.config_path` — reviewed one-off config override path; normal runs use this folder's `config.json`.

## Config defaults

- `bar_grain`
- `lookback_intervals`
- return/volume/relative-strength/gap/liquidity thresholds
- price-action thresholds for false breakouts, failed breakdowns, liquidity sweeps, bull traps, and bear traps
- `model_standard` — default `equity_abnormal_activity_conservative`
- `calibration_status` — default marks the standard as conservative fixture/default behavior, not production-calibrated label evidence

## Output

`saved/equity_abnormal_activity_event.csv` with compact event-style rows for abnormal price, volume, relative-strength, gap, liquidity, and price-action behavior. Full details remain in evidence/reference fields rather than being duplicated as upstream model features.

## Production rule

The default is intentionally conservative. It may produce prior-signal event evidence for local development and model-design fixtures, but training labels or promoted production gates must cite a reviewed historical calibration report before overriding thresholds or treating `equity_abnormal_activity_conservative` as production-calibrated.
