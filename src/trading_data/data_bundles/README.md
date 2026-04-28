# data_bundles

Manager-facing task bundles live here.

Boundary:

- `trading_data.data_sources.*` owns the smallest reusable data acquisition / source normalization interfaces.
- `trading_data.data_bundles.*` accepts manager-issued task keys, chooses the required source interfaces, applies reviewed code-level contracts/defaults, and writes task-run outputs/receipts.
- Model input generation belongs here, not in `data_sources`, because it composes multiple source outputs and model-layer boundaries.

Current model-input/data-product bundles:

Note: `TradeQualityModel` currently does not need a `trading-data` bundle because it consumes upstream SQL outputs and model/strategy candidates without new data acquisition.

- `01_market_regime_model_inputs` — MarketRegimeModel ETF bar SQL long table over the manager-supplied time range; ETF universe and grains come from `market_etf_universe.csv`.
- `02_security_selection_model_inputs` — SQL-only filtered US-listed equity ETF holdings table for SecuritySelectionModel; ETF universe comes from `market_etf_universe.csv`.
- `03_strategy_selection_model_inputs` — SQL-only manager-selected symbol bar/liquidity table for StrategySelectionModel; defaults to 1Min.
- `05_option_expression_model_inputs` — SQL-only ThetaData option-chain snapshot table for OptionExpressionModel; still scheduled for contract-level entry/exit snapshot revision.
- `06_position_execution_model_inputs` — SQL-only selected option contract time-series table for PositionExecutionModel; covers entry through exit plus one hour.
- `07_event_overlay_model_inputs` — SQL-only EventOverlayModel overview table; one row per event, with details behind references.
- `07_event_overlay_model_inputs/equity_abnormal_activity` — nested event-overlay detector for equity/ETF abnormal activity evidence rows.

The remaining historical acquisition runners still live under `data_sources` until each has a reviewed manager-facing wrapper. Do not add new model-input generation under `data_sources`.
