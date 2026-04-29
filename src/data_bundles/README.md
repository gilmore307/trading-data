# data_bundles

Manager-facing task bundles live here.

Boundary:

- `data_sources.*` owns the smallest reusable data acquisition / source normalization interfaces.
- `data_bundles.*` accepts manager-issued task keys, chooses the required source interfaces, applies reviewed code-level contracts/defaults, and writes task-run outputs/receipts.
- Model-layer data acquisition/preparation belongs here, not in `data_sources`, because it composes source outputs around manager-facing bundle boundaries.

Current numbered data bundles:

Note: `TradeQualityModel` currently does not need a `trading-source` bundle because it consumes upstream SQL outputs and model/strategy candidates without new data acquisition.

- `01_bundle_market_regime` — MarketRegimeModel ETF bar SQL long table over the manager-supplied time range; ETF universe and grains come from `market_etf_universe.csv`.
- `02_bundle_security_selection` — SQL-only filtered US-listed equity ETF holdings table for SecuritySelectionModel; ETF universe comes from `market_etf_universe.csv`.
- `03_bundle_strategy_selection` — SQL-only manager-selected symbol bar/liquidity table for StrategySelectionModel; defaults to 1Min.
- `05_bundle_option_expression` — SQL-only contract-level ThetaData option-chain snapshot table for OptionExpressionModel; one row per visible contract per entry/exit snapshot.
- `06_bundle_position_execution` — SQL-only selected option contract time-series table for PositionExecutionModel; covers entry through exit plus one hour.
- `07_bundle_event_overlay` — SQL-only EventOverlayModel overview table; one row per event, with details behind references.
- `07_bundle_event_overlay/equity_abnormal_activity` — nested event-overlay detector for equity/ETF abnormal activity evidence rows.

The remaining historical acquisition runners still live under `data_sources` until each has a reviewed manager-facing wrapper. Do not add new model-layer data preparation under `data_sources`, and do not name active bundle packages `*_model_inputs`.
