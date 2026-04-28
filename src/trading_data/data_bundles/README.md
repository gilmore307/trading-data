# data_bundles

Manager-facing task bundles live here.

Boundary:

- `trading_data.data_sources.*` owns the smallest reusable data acquisition / source normalization interfaces.
- `trading_data.data_bundles.*` accepts manager-issued task keys, chooses the required source interfaces, applies that bundle's local `config.json`, and writes task-run outputs/receipts.
- Model input generation belongs here, not in `data_sources`, because it composes multiple source outputs and model-layer configuration.

Current model-input bundles:

- `stock_etf_exposure` — ETF holdings snapshots + `stock_etf_exposure/config.json` ETF universe / issuer / score defaults -> `stock_etf_exposure.csv`.
- `equity_abnormal_activity` — equity bars + optional benchmark/liquidity inputs + `equity_abnormal_activity/config.json` detector defaults -> `equity_abnormal_activity_event.csv`.

The remaining historical acquisition runners still live under `data_sources` until each has a reviewed manager-facing wrapper. Do not add new model-input generation under `data_sources`.
