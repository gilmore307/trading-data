# Source Outputs For Model Layers

This document maps `trading-data` source-backed outputs to accepted `trading-model` layers and downstream model consumers. It is an organization contract for external/source observations, not a complete training-data or derived-data plan.

## Principles

- Keep raw/source acquisition in smallest-unit modules under `src/data_feed/`.
- Keep control-plane-facing model-input orchestration under `src/data_source/`.
- Keep task inputs in control-plane task keys, stable source contracts/defaults in code, and shared reviewed universes in shared artifacts; avoid source-local config files unless operators must routinely change the value outside code review.
- Keep final model-facing outputs SQL-only for accepted numbered data sources.
- Preserve point-in-time semantics. Model inputs must not use information unavailable at decision time.
- Keep model outputs, model-evaluation labels, training runs, action/backtest artifacts, and promotion decisions outside `trading-data`. This repository may perform feed acquisition, source construction, and deterministic point-in-time feature construction needed by models.
- Register reusable names through `trading-manager` before other repositories depend on them.

## Layer Artifact Naming

Current layer artifacts use the pattern:

```text
source_NN_<layer_slug>
feature_NN_<layer_slug>
model_NN_<layer_slug>
model_NN_<layer_slug>_explainability
model_NN_<layer_slug>_diagnostics
```

`trading-data` owns `source` and `feature` artifacts only. Layer-owned fields use compact numeric prefixes such as `1_*` and `2_*` when they represent reviewed layer concepts; raw/source observation fields may remain generic. Do not introduce `layer01_*` or `layer02_*` aliases for the same concept.

## Layer Input Sources

| Model layer | Input source | Core data products | Notes |
|---|---|---|---|
| `MarketRegimeModel` | `source_01_market_regime` | ETF/broad-market bars | Alpaca is the primary source for ETF bars. ETF holdings are not required for the first regime model except as explanatory metadata. |
| `SectorContextModel` | `feature_02_sector_context` | sector/industry rotation, trend, volatility, correlation, breadth, and dispersion evidence | Feeds Layer 2 `sector_context_state`; ETF holdings are not a core Layer 2 behavior-model input. |
| Anonymous target candidate builder / Layer 3 input preparation | `source_02_target_candidate_holdings` | filtered US-listed ETF holdings for Layer 2 selected/prioritized sector baskets | Downstream sector-to-stock transmission evidence, not Layer 2 core behavior input. |
| `TargetStateVectorModel` | `source_03_target_state` | candidate-symbol bars, liquidity, and point-in-time target-local evidence | Candidate symbols should be produced from Layer 2 selected baskets by the anonymous target candidate builder, then anonymized for target state-vector construction. |
| `EventOverlayModel` | `source_04_event_overlay` | one-row-per-event overview table | Combines lagging evidence and prior-signal events while details remain behind URL/path references; `trading-model` builds `event_context_vector` from this point-in-time index plus reviewed context states/artifacts. |
| `AlphaConfidenceModel` | _(no trading-data source)_ | `target_context_state`, `event_context_vector`, upstream context, realized outcomes/labels | Does not require new source acquisition, SQL view, or manifest contract in `trading-data`; labels belong outside inference features and are materialized only through reviewed deterministic evaluation contracts. |
| `TradingProjectionModel` | _(no trading-data source)_ | alpha/confidence state, costs, risk budget, current/pending position state | Converts confidence into offline target action/exposure outside `trading-data`. |
| `OptionExpressionModel` | `source_05_option_expression` | contract-level option-chain snapshots at entry/exit decision points | Chooses theoretically best-return and most risk-controllable long call / long put contracts from one row per visible contract per snapshot. |
| `PositionExecutionModel` | `source_06_position_execution` | selected-contract option time series | Studies how to execute the selected contracts from entry through exit plus one hour. |

## Implemented Model Input Sources

Each accepted model layer that needs new `trading-data` acquisition has a control-plane-facing source-backed source under `src/data_source/source_NN_<layer_slug>/`. These sources fetch/prepare external observations needed by the layer; they are not the complete model-input or training-data universe.

Layer 1 accepts `params.start` and `params.end`, reads the reviewed `market_regime_etf_universe.csv` for ETF scope and bar grains, fetches Alpaca bars, and writes one combined SQL long table, `source_01_market_regime`.

Layer 2 feature construction reads cleaned Layer 1 bar rows plus reviewed relative-strength combinations and writes `feature_02_sector_context`. It owns deterministic point-in-time evidence for sector/industry behavior under market context: relative strength, normalized trend distance/slope/spread/alignment, volatility ratio, correlation, breadth, and dispersion. It does not consume ETF holdings or `stock_etf_exposure` as core behavior-model inputs.

The downstream target-candidate preparation boundary accepts `params.start` and `params.end`, reads the reviewed `market_regime_etf_universe.csv` for ETF scope/issuer/exposure labels, keeps only `universe_type = sector_observation_etf` for holdings analysis, collects ETF holdings snapshots, filters them to US-listed equity constituents only, and writes SQL table `source_02_target_candidate_holdings`. Its semantic owner is the anonymous target candidate builder / Layer 3 input-preparation boundary after Layer 2 has selected/prioritized sector baskets.

Layer 3 has two target-state surfaces with different maturity.

Raw target-local observed inputs remain source-scoped: candidate-builder-supplied `params.start`, `params.end`, and `params.symbols` default to 1Min, fetch Alpaca bars plus transient trade/quote liquidity inputs, and should write SQL table `source_03_target_state`.

Target state-vector construction is feature-scoped: `trading-manager` issues a request with a reviewed window, anonymous candidate-universe reference, Layer 1/2 state references, and output target; `trading-data` builds deterministic market/sector/target/cross-state feature blocks and writes `feature_03_target_state_vector`. `trading-model` consumes that surface to train/evaluate `TargetStateVectorModel` against market-only and market+sector baselines.

Layer 4 accepts `params.start`, `params.end`, focus sectors/symbols, and event overview rows, then writes SQL table `source_04_event_overlay`, one row per event. Full news, SEC, macro, abnormal-activity detector, revision, and timeline details remain behind references. `source_04_event_overlay` is an event index; `trading-model` builds `event_context_vector` by combining these point-in-time rows with event artifacts, upstream `market_context_state` / `sector_context_state` / `target_context_state` references, and reviewed scope/sensitivity metadata.

`source_05_option_expression` accepts manager-supplied `params.underlying`, `params.snapshot_time`, and optional `params.snapshot_type` (`entry`/`exit`, default `entry`), calls the ThetaData option selection snapshot interface, and writes one row per visible option contract per snapshot. `snapshot_time` is the point-in-time clock; quote/IV/Greeks provider row timestamps are intentionally omitted from the business table. Despite the `source_05_` prefix, this is an option-expression source for the downstream `OptionExpressionModel`, not the model Layer 5 `AlphaConfidenceModel`.

`source_06_position_execution` accepts `params.selected_contracts` from the expression/projection handoff and writes selected option contract market data from entry time through exit time plus one hour.

## Source-Backed Aggregations That Need Migration Review

### `stock_etf_exposure`

Integrated step: `src/data_source/source_02_target_candidate_holdings/pipeline.py`

Purpose: point-in-time stock-to-ETF exposure evidence for the anonymous target candidate builder / Layer 3 input-preparation boundary.

It derives from issuer-published `etf_holding_snapshot` rows and reviewed upstream basket context. It lets downstream candidate construction transmit Layer 2 selected/prioritized ETF/sector/industry baskets into a stock candidate universe before Layer 3 target-state construction anonymizes model-facing target vectors.

Important fields:

- `as_of_date`
- `symbol`
- `exposed_etfs`
- `top_exposure_etf`
- `total_etf_exposure_score`
- `weighted_sector_score`
- `weighted_theme_score`
- `exposure_tags`
- `source_etf_count`
- `source_snapshot_refs`
- `available_time`

Boundary:

- Source-backed aggregation, not a raw provider table.
- Must preserve `available_time`; do not assume a holdings file is usable before it was visible.
- Not a Layer 2 core behavior-model input.
- Future stock-level exposure features that combine source holdings with model scores need explicit boundary review; deterministic source-derived features may live in `trading-data`, while model-derived scores belong in `trading-model`.

### `equity_abnormal_activity_event`

Source: `src/data_source/source_04_event_overlay/equity_abnormal_activity/`

Config: `src/data_source/source_04_event_overlay/equity_abnormal_activity/config.json`

Purpose: EventOverlayModel prior-signal row for abnormal stock/ETF price, volume, relative-strength, gap, or liquidity behavior.

It is analogous to option activity events but uses equity/ETF market data:

- return z-score
- volume z-score
- relative strength z-score versus benchmark/sector ETF
- gap percentage
- spread/liquidity abnormality
- evidence window and source refs

Boundary:

- Source-backed event-style aggregation, not raw trades/quotes.
- Should be created only from observable market data at/after the event effective time.
- Implemented first as a conservative detector over saved `equity_bar.csv`, optional benchmark bars, and optional `equity_liquidity_bar.csv` inputs.
- If this becomes a generated signal/candidate/label rather than source evidence, move it to `trading-data`.

## Known Open Data Gaps

- Keep `source_05_option_expression` documented as source-number 05 for option-expression input, not as model Layer 5 `AlphaConfidenceModel` acquisition.
- Clean accepted SQL business tables so `run_id`, `task_id`, and write audit timestamps stay in receipts/run metadata rather than business rows.
- Harden ETF-symbol-to-issuer mapping and ETF holdings freshness/available-time rules for production runs.
- Calibrate equity abnormal activity thresholds/model standards against historical distributions before training labels consume them.
- Define optionability summary shape for SectorContextModel; likely derived from option chain snapshots and liquidity filters.
