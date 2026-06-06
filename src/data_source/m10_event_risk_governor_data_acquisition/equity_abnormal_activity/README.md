# m10_event_risk_governor_data_acquisition/equity_abnormal_activity

Derived event detector inside the `m10_event_risk_governor_data_acquisition` Layer 10 EventRiskGovernor surface. This is not a standalone manager-facing numbered data source.

It converts SQL-retained equity/ETF bars, optional reference bars, and optional liquidity rows into compact `equity_abnormal_activity_event` evidence rows inside the Layer 10 event-risk evidence surface. Layer 4 may consume only reviewed/promoted evidence packets, not raw abnormal-activity rows.

## Inputs

- `params.bars_sql_source` — preferred production input, pointing at `trading_data.m01_market_regime_data_acquisition` with `source_symbol`, `timeframe`, `start`, and `end`.
- `params.bars_csv_path` — local fixture/debug input only; production Alpaca bars are retained in SQL and do not require saved `equity_bar.csv`.
- `params.reference_bars_csv_path` — optional reference/sector ETF bar CSV path for controlled detector experiments.
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
