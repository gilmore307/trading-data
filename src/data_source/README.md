# data_source

Manager-facing task sources live here.

Boundary:

- `data_feed.*` owns the smallest reusable data acquisition / source normalization interfaces.
- `data_source.*` accepts manager-issued task keys, chooses the required feed interfaces, applies reviewed code-level contracts/defaults, and writes task-run outputs/receipts.
- Model-layer data acquisition/preparation belongs here, not in `data_feed`, because it composes source outputs around manager-facing source boundaries.

Current numbered data sources:

Note: `TradeQualityModel` currently does not need a `trading-data` source because it consumes upstream SQL outputs and model/strategy candidates without new data acquisition.

- `source_01_market_regime` — MarketRegimeModel ETF bar SQL long table over the manager-supplied time range; ETF universe and grains come from `market_regime_etf_universe.csv`.
- `source_02_security_selection` — SQL-only filtered US-listed equity ETF holdings table for SecuritySelectionModel; ETF universe comes from `market_regime_etf_universe.csv`.
- `source_03_strategy_selection` — SQL-only manager-selected symbol bar/liquidity table for StrategySelectionModel; defaults to 1Min.
- `source_05_option_expression` — SQL-only contract-level ThetaData option-chain snapshot table for OptionExpressionModel; one row per visible contract per entry/exit snapshot.
- `source_06_position_execution` — SQL-only selected option contract time-series table for PositionExecutionModel; covers entry through exit plus one hour.
- `source_07_event_overlay` — SQL-only EventOverlayModel overview table; one row per event, with details behind references.
- `source_07_event_overlay/equity_abnormal_activity` — nested event-overlay detector for equity/ETF abnormal activity evidence rows.

The remaining historical acquisition runners still live under `data_feed` until each has a reviewed manager-facing wrapper. Do not add new model-layer data preparation under `data_feed`, and do not name active source packages `*_model_inputs`.
