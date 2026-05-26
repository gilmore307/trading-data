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

SQL table surfaces use the shared owner-domain-stage pattern from `trading-manager/scripts/registry/rules/model-layer-naming.md`:

```text
<schema>.<owner_prefix>_<domain_slug>_<task_stage>[_<artifact_role>]
```

`trading-data` owns data-acquisition and deterministic feature-generation surfaces. Use model prefixes when the data surface is generated for a reviewed model layer:

```text
trading_data.m01_market_regime_data_acquisition
trading_data.m01_market_regime_feature_generation
```

SQL identifiers stay lowercase snake_case. Use `.` only for SQL namespace separation such as `schema.table`; do not create three-part pseudo-names such as `trading_data.m01_market_regime.data_acquisition`, and do not use hyphens in SQL identifiers.

Old `source_NN_*`, `feature_NN_*`, and `model_NN_*` names are migration debt, not current planning names.

`trading-data` owns source/data-acquisition and feature-generation artifacts only. Layer-owned fields use compact numeric prefixes such as `1_*` and `2_*` when they represent reviewed layer concepts; raw/source observation fields may remain generic. Do not introduce `layer01_*` or `layer02_*` aliases for the same concept.

## Layer Input Sources

| Model layer | Input source | Core data products | Notes |
|---|---|---|---|
| `MarketRegimeModel` | `trading_data.m01_market_regime_data_acquisition` | ETF/broad-market bars | Alpaca is the primary source for ETF bars. ETF holdings are not required for the first regime model except as explanatory metadata. Layer 1 source/features must preserve input-frame identity so `trading-model` can pair `1min`, `10min`, `1h`, and `1D` market contexts with the canonical `10min`, `1h`, `1D`, and `1W` prediction horizons. |
| `SectorContextModel` | `trading_data.m02_sector_context_feature_generation` | sector/industry rotation, trend, volatility, correlation, breadth, and dispersion evidence | Feeds Layer 2 `sector_context_state`; ETF holdings are not a core Layer 2 behavior-model input. |
| Anonymous target candidate builder / Layer 3 input preparation | `trading_data.m02_sector_context_data_acquisition` | filtered US-listed ETF holdings for Layer 2 selected/prioritized sector baskets | Materialized by the Layer 2 feature stage; consumed by downstream target-candidate preparation, not by the core SectorContextModel. |
| `TargetStateVectorModel` | `trading_data.m03_target_state_vector_data_acquisition` | candidate-symbol bars, liquidity, and point-in-time target-local evidence | Candidate symbols should be produced from Layer 2 selected baskets by the anonymous target candidate builder, then anonymized for target state-vector construction. |
| `EventFailureRiskModel` | _(no dedicated trading-data source/feature)_ | reviewed event/strategy-failure evidence refs and `event_failure_risk_vector` conditioning | Layer 4 consumes reviewed governance/model evidence; raw event acquisition does not become a symmetric trading-data source by default. |
| `AlphaConfidenceModel` | _(no trading-data source/feature)_ | `target_context_state`, `event_failure_risk_vector`, upstream context, realized outcomes/labels | Does not require new source acquisition, feature package, SQL view, or manifest contract in `trading-data`; labels belong outside inference features and are materialized only through reviewed deterministic evaluation contracts. |
| `PositionProjectionModel` | _(no trading-data source/feature)_ | final adjusted `alpha_confidence_vector`, costs, risk budget, current/pending position state | Projects target holding state and abstract target exposure outside `trading-data`; it does not produce buy/sell/hold or execution instructions. |
| `UnderlyingActionModel` | _(no trading-data source/feature)_ | `position_projection_vector`, upstream context, action-policy context | Offline underlying-action recommendation is model/control-plane work; no deterministic source-derived feature package is owned here. |
| `OptionExpressionModel` | `trading_data.m09_option_expression_data_acquisition`, `trading_data.m09_option_expression_feature_generation` | contract-level option-chain snapshots and deterministic option-candidate feature payloads at entry/exit decision points | `trading-data` prepares moneyness, spread/liquidity, IV, Greeks, and quality payloads; `trading-model` owns contract ranking and expression choice. |
| `OptionExpressionModel` replay/evaluation | `trading_data.m09_option_expression_data_acquisition_contract_path` | selected option contract time series | Tracks the market path of selected contracts from entry through exit plus one hour; this is option-contract path data for replay/evaluation, not a broker execution table. |
| `EventRiskGovernor` | `trading_data.m10_event_risk_governor_data_acquisition`, `trading_data.m10_event_risk_governor_feature_generation` | one-row-per-observed-event/evidence overview table plus deterministic event-overview feature payloads | Combines lagging evidence and prior-signal events while details remain behind URL/path references; canonical-event/dedup fields prevent derivative coverage from becoming duplicate alpha; `trading-model` builds Layer 10 event-risk context from this feature surface plus reviewed context states/artifacts and the Layer 8 thesis. |

## Implemented Model Input Sources

Each accepted model layer that needs new `trading-data` acquisition has a control-plane-facing data-acquisition or feature-generation table. These sources fetch/prepare external observations needed by the layer; they are not the complete model-input or training-data universe.

Layer 1 accepts `params.start` and `params.end`, reads the reviewed `layer_01_02_market_context_etf_universe.csv` for ETF scope and bar grains, fetches Alpaca bars, and writes one combined SQL long table, `trading_data.m01_market_regime_data_acquisition`. Its feature construction writes `trading_data.m01_market_regime_feature_generation` and must keep market-context input frames separate. The accepted training/evaluation pairing is `1min -> 10min`, `10min -> 1h`, `1h -> 1D`, and `1D -> 1W`. Future outcomes for those horizons are labels/evaluation indicators, not inference features.

Layer 2 feature construction reads cleaned Layer 1 bar rows plus reviewed relative-strength combinations and writes `trading_data.m02_sector_context_feature_generation`. It owns deterministic point-in-time evidence for sector/industry behavior under market context: relative strength, normalized trend distance/slope/spread/alignment, volatility ratio, correlation, breadth, and dispersion. The same Layer 2 stage also materializes `trading_data.m02_sector_context_data_acquisition` after sector/basket context is available; those holdings rows are downstream candidate-preparation inputs, not core behavior-model inputs.

`trading_data.m02_sector_context_data_acquisition` accepts `params.start` and `params.end`, reads the reviewed `layer_01_02_market_context_etf_universe.csv` for ETF scope/issuer/exposure labels, keeps only `universe_type = sector_observation_etf` for holdings analysis, collects ETF holdings snapshots, filters them to US-listed equity constituents only, and writes the candidate-pool acquisition rows. Its runtime owner is the Layer 2 stage so candidate inputs are ready before Layer 3 target-state construction.

ETF holdings coverage is allowed to be partial. When an official issuer route is known but has no rows inside the point-in-time window, or a bounded issuer fetch fails under `continue_on_error`, the source records per-symbol coverage diagnostics and `missing_symbols` instead of fabricating holdings rows or failing the entire Layer 2 handoff. Downstream models must tolerate a missing subset of ETF holdings evidence; missing coverage is evidence quality, not a synthetic constituent signal.

Layer 3 has two target-state surfaces with different maturity.

Raw target-local observed inputs remain source-scoped: candidate-builder-supplied candidate rows plus reviewed local bar/liquidity artifacts are normalized into SQL table `trading_data.m03_target_state_vector_data_acquisition`. Alpaca acquisition for these candidate-dependent rows is deferred until the manager supplies the candidate universe and bounded feed artifacts.

Target state-vector construction is feature-scoped: `trading-manager` issues a request with a reviewed window, anonymous candidate-universe reference, Layer 1/2 state references, and output target; `trading-data` builds deterministic market/sector/target/cross-state feature blocks and writes `trading_data.m03_target_state_vector_feature_generation`. `trading-model` consumes that surface to train/evaluate `TargetStateVectorModel` against market-only and market+sector baselines.

Layer 10 event-risk accepts `params.start`, `params.end`, focus sectors/symbols, and event overview rows, then writes SQL table `trading_data.m10_event_risk_governor_data_acquisition`, one row per observed event/evidence row. It stores `canonical_event_id`, `dedup_status`, `source_priority`, `coverage_reason`, and `covered_by_event_id` so SEC/company/regulatory canonical events can cover derivative news without double-counting event presence or alpha factors. Full news, SEC, macro, abnormal-activity detector, browser/agent analysis, revision, and timeline details remain behind references. Earnings/guidance scouting rows are now materialized as `earnings_guidance` overview rows: Nasdaq/calendar artifacts are scheduled shells only, while SEC/company official artifacts are result/guidance evidence. Calendar and market-structure rows such as holidays, early closes, long weekends, option-expiry/triple-witching windows, and index rebalance windows are global event-pool observations until Layer 10 promotes a plausible relationship into the focused/watched event pool for systematic acquisition, offline Layer 4 candidate training, and Layer 5 validation. Persistent-regime rows such as pandemic, tariff-war, geopolitical war/escalation, sanctions, banking-system stress, or policy crisis periods preserve point-in-time interval facts and may remain active/shadow-active without same-day news. `trading_data.m10_event_risk_governor_feature_generation` turns accepted overview rows into deterministic source-only event-category, scope, dedup, source-priority, and quality payloads. `trading-model` builds `event_context_vector` by combining this point-in-time feature surface with event artifacts, upstream `market_context_state` / `sector_context_state` / `target_context_state` references, and reviewed scope/sensitivity metadata.

Historical and realtime/future event acquisition source priority is governed by `docs/23_event_source_registry.md`. Macro event observations use the canonical Trading Economics storage snapshot as accepted source evidence; the TE website route is retired. Persistent regimes are promoted from repeated high-frequency news topics through agent review before becoming `persistent_event_regime` interval rows.

`trading_data.m09_option_expression_data_acquisition` accepts manager-supplied `params.underlying`, `params.snapshot_time`, and optional `params.snapshot_type` (`entry`/`exit`, default `entry`), calls the ThetaData option selection snapshot interface, and writes one row per visible option contract per snapshot. `snapshot_time` is the point-in-time clock; quote/IV/Greeks provider row timestamps are intentionally omitted from the business table. `trading_data.m09_option_expression_feature_generation` turns accepted snapshot rows into deterministic source-only option-candidate payloads for moneyness, spread/liquidity, IV, Greeks, and quality diagnostics.

`trading_data.m09_option_expression_data_acquisition_contract_path` accepts `params.selected_contracts` from the option-expression handoff and writes selected option contract market data from entry time through exit time plus one hour. It emits market data only and must not produce execution instructions, order fields, PnL labels, or model outputs.

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
- Stock-level exposure features that combine source holdings with model scores require explicit boundary review: deterministic source-derived features may live in `trading-data`; model-derived scores belong in `trading-model`.

### `equity_abnormal_activity_event`

Source: `src/data_source/source_10_event_risk_governor/equity_abnormal_activity/`

Config: `src/data_source/source_10_event_risk_governor/equity_abnormal_activity/config.json`

Purpose: residual/trigger evidence for abnormal stock/ETF board/tape behavior when the event-risk path needs a point-in-time evidence row that is not merely a duplicate of ordinary bar/liquidity features already consumed by the base model stack.

It is analogous to option activity events but uses equity/ETF market data only as detector evidence.

Accepted abnormal-activity evidence categories:

```text
price_action_pattern
residual_market_structure_disturbance
microstructure_liquidity_disruption
option_derivatives_abnormality
```

Typical source evidence:

- detector-trigger return/volume/relative-strength/gap/spread evidence refs;
- residual abnormality flags after conditioning on upstream market/sector/target state, when reviewed;
- false breakout / failed breakdown / liquidity sweep / bull-trap / bear-trap price-action tokens;
- spread widening, depth/quote-quality disruption, halt/pause/anomalous quote evidence, when source-visible;
- option IV/skew/term-structure/volume/OI/liquidity abnormality refs, when accepted as not already consumed by the base option-expression path;
- evidence window, detector standard, and source refs.

Boundary:

- Source-backed event-style aggregation, not raw trades/quotes.
- Should be created only from observable market data at/after the event effective time.
- Must not duplicate ordinary `equity_bar`, `equity_liquidity_bar`, volatility, gap, volume, spread, trend, or target-state features that already feed Layer 1-3 or the base trading-guidance path.
- Implemented first as a conservative detector over saved `equity_bar.csv`, optional reference bars, and optional `equity_liquidity_bar.csv` inputs. Those inputs are provenance for a compact event token/residual evidence row, not permission to re-emit the same bar-derived fields as independent event alpha.
- Price-action tokens are detector evidence for Layer 10 event-risk governance; they are not a separate model layer, trading action, or production-calibrated label without reviewed historical evidence.
- If this becomes a generated signal, candidate decision, or label rather than source evidence, move that behavior out of `trading-data` and into the owning model/evaluation boundary.

### `event_activity_bridge` evidence refs

`event_activity_bridge` is model-owned, but `trading-data` may provide point-in-time evidence refs that support it. Current model evidence shows raw option abnormality plus raw news proximity is too broad for promotion; future bridge work must route through reviewed event-family scouting packets rather than headline-only family guesses. Startup abnormality scope is restricted to compact non-overlapping/residual detector refs; duplicated upstream feature payloads, strategy-failure labels, and post-event realized labels are excluded.

- event evidence refs: news, SEC/company disclosure, macro/calendar, official data, or hard-to-standardize narrative artifacts;
- price activity refs: compact residual/price-action evidence, not duplicated bar features, and only with an upstream non-overlap/residual audit trail;
- liquidity activity refs: spread/depth/quote-quality/halt-pause evidence that is not already represented by upstream liquidity/context features for the same decision context;
- option activity refs: IV/skew/term-structure/volume/OI/liquidity evidence when not already consumed as base option-expression inputs, or when explicitly marked residual after that upstream path;
- prediction-market activity refs: future Polymarket-style odds/volume/liquidity refs, when that source boundary is accepted.

The bridge is useful when raw news is too ambiguous to standardize confidently but market/odds activity provides stable lead-lag or confirmation/divergence evidence. `trading-data` preserves refs, clocks, and non-overlap/provenance evidence; `trading-model` owns bridge scoring and interpretation.

## Current Guardrails

- `trading_data.m09_option_expression_data_acquisition` is the option-expression input surface; it is not Layer 5 `AlphaConfidenceModel` acquisition.
- SQL business tables keep `run_id`, `task_id`, and write audit timestamps in receipts/run metadata rather than business rows.
- ETF holdings freshness is conservative by default: explicit source/task `available_time` wins; otherwise holdings become visible at the next regular US session open after `as_of_date`.
- `equity_abnormal_activity_event` default standard is `equity_abnormal_activity_conservative`; production labels or promoted gates require reviewed historical calibration evidence before threshold changes are trusted.
- Optionability summary shape should be defined only when the model/control-plane contract needs a durable shared interface.
