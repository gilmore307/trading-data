# data_source

Manager-facing task sources live here.

Boundary:

- `data_feed.*` owns the smallest reusable data acquisition / source normalization interfaces.
- `data_source.*` accepts manager-issued task keys, chooses the required feed interfaces, applies reviewed code-level contracts/defaults, and writes task-run outputs/receipts.
- Model-layer data acquisition/preparation belongs here, not in `data_feed`, because it composes source outputs around manager-facing source boundaries.

Current numbered data sources are cataloged in `src/data_layers/catalog.py` and summarized here:

Note: Layers 5-7 currently do not need new `trading-data` sources because they consume upstream SQL outputs, model outputs, labels, position/risk/control-plane context, and reviewed evaluation artifacts without new source acquisition.

- `m01_market_regime_data_acquisition` — MarketRegimeModel ETF bar SQL long table over the manager-supplied time range; ETF universe and grains come from `layer_01_02_market_context_etf_universe.csv`.
- `m02_sector_context_data_acquisition` — SQL-only filtered US-listed equity ETF holdings table materialized by the Layer 2 feature stage for anonymous target candidate preparation; ETF universe comes from `layer_01_02_market_context_etf_universe.csv`.
- `m03_target_state_vector_data_acquisition` — SQL-only target-local bar/liquidity input table for anonymous target state-vector construction.
- `m10_event_risk_governor_data_acquisition` — SQL-only EventRiskGovernor overview table; one row per event, with details behind references.
- `m10_event_risk_governor_data_acquisition/equity_abnormal_activity` — nested event-risk detector package for equity/ETF abnormal activity evidence rows.
- `m09_option_expression_data_acquisition` — SQL-only contract-level ThetaData option-chain snapshot table for OptionExpressionModel; one row per visible contract per entry/exit snapshot.
- `m09_option_expression_data_acquisition_contract_path` — SQL-only selected option contract time-series source for OptionExpressionModel replay/evaluation; covers entry through exit plus one hour and emits market data only.

Feed-level runners stay under `data_feed` until a reviewed manager-facing source composes them. Do not add new model-layer data preparation under `data_feed`, and do not name active source packages `*_model_inputs`.
