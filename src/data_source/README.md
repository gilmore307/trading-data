# data_source

Manager-facing task sources live here.

Boundary:

- `data_feed.*` owns the smallest reusable data acquisition / source normalization interfaces.
- `data_source.*` accepts manager-issued task keys, chooses the required feed interfaces, applies reviewed code-level contracts/defaults, and writes task-run outputs/receipts.
- Model-layer data acquisition/preparation belongs here, not in `data_feed`, because it composes source outputs around manager-facing source boundaries.

Current numbered data sources:

Note: downstream alpha/projection consumers currently do not need new `trading-data` sources because they consume upstream SQL outputs, model outputs, labels, and reviewed evaluation artifacts without new source acquisition.

- `source_01_market_regime` — MarketRegimeModel ETF bar SQL long table over the manager-supplied time range; ETF universe and grains come from `market_regime_etf_universe.csv`.
- `source_02_target_candidate_holdings` — SQL-only filtered US-listed equity ETF holdings table for anonymous target candidate preparation after Layer 2 sector/basket prioritization; ETF universe comes from `market_regime_etf_universe.csv`.
- `source_03_target_state` — SQL-only target-local bar/liquidity input table for anonymous target state-vector construction.
- `source_04_event_overlay` — SQL-only EventOverlayModel overview table; one row per event, with details behind references.
- `source_04_event_overlay/equity_abnormal_activity` — nested event-overlay detector for equity/ETF abnormal activity evidence rows.
- `source_05_option_expression` — SQL-only contract-level ThetaData option-chain snapshot table for OptionExpressionModel; one row per visible contract per entry/exit snapshot.
- `source_06_position_execution` — SQL-only selected option contract time-series source for OptionExpressionModel replay/evaluation; covers entry through exit plus one hour and emits market data only.

Feed-level runners stay under `data_feed` until a reviewed manager-facing source composes them. Do not add new model-layer data preparation under `data_feed`, and do not name active source packages `*_model_inputs`.
