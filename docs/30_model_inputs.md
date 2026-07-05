# Source Outputs For Models

This document maps `trading-data` source-backed outputs to accepted `trading-model` M01- consumers. It is an organization contract for external/source observations, not a complete training-data or derived-data plan.

## Principles

- Keep raw/source acquisition in smallest-unit modules under `src/data_feed/`.
- Keep control-plane-facing model-input orchestration under `src/data_source/`.
- Keep task inputs in control-plane task keys, stable source contracts/defaults in code, and shared reviewed universes in shared artifacts; avoid source-local config files unless operators must routinely change the value outside code review.
- Keep final model-facing outputs SQL-only for accepted numbered data sources.
- Preserve point-in-time semantics. Model inputs must not use information unavailable at decision time.
- Keep model outputs, model-evaluation labels, training runs, action/backtest artifacts, and promotion decisions outside `trading-data`. This repository may perform feed acquisition, source construction, and deterministic point-in-time feature construction needed by models.
- Register reusable names through `trading-manager` before other repositories depend on them.

## Model Artifact Naming

SQL table surfaces use the shared owner-domain-stage pattern from `trading-manager/scripts/registry/rules/model-naming.md`:

```text
<schema>.<owner_prefix>_<domain_slug>_<task_stage>[_<artifact_role>]
```

`trading-data` owns data-acquisition and deterministic feature-generation surfaces. Use model prefixes when the data surface is generated for a reviewed model:

```text
trading_data.model_01_market_regime_data_acquisition
trading_data.model_01_market_regime_feature_generation
```

SQL identifiers stay lowercase snake_case. Use `.` only for SQL namespace separation such as `schema.table`; do not create three-part pseudo-names such as `trading_data.model_01_market_regime.data_acquisition`, and do not use hyphens in SQL identifiers.

Old `source_NN_*`, `feature_NN_*`, and `model_NN_*` names are migration debt, not current planning names.

`trading-data` owns source/data-acquisition and feature-generation artifacts only. Model-owned fields use compact numeric prefixes such as `1_*` and `2_*` when they represent reviewed model concepts; raw/source observation fields may remain generic. Do not introduce `layer01_*` or `layer02_*` aliases for the same concept.

## Model Input Sources

| Model | Input source | Core data products | Notes |
|---|---|---|---|
| `MarketRegimeModel` | `trading_data.model_01_market_regime_data_acquisition` | ETF/broad-market bars | Alpaca is the primary source for ETF bars. ETF holdings are not required for the first regime model except as explanatory metadata. M01 source/features must preserve input-frame identity so `trading-model` can pair `1min`, `10min`, `1h`, and `1D` market contexts with the canonical `10min`, `1h`, `1D`, and `1W` prediction horizons. |
| `SectorContextModel` | `trading_data.model_02_sector_context_feature_generation` | broad sector-anchor rotation, trend, volatility, correlation, breadth, and dispersion evidence | Feeds M02 `sector_context_state`; focused industry/theme ETFs and ETF holdings are not core M02 behavior-model inputs. |
| `TargetStateVectorModel` | `trading_data.model_03_target_state_vector_data_acquisition` | candidate-symbol bars, liquidity, point-in-time target-local evidence, and attached broad sector context | Candidate symbols come from the reviewed total-symbol pool and target metadata, not from M02 ETF holdings. |
| `EventFailureRiskModel` | _(no dedicated trading-data source/feature)_ | reviewed event/strategy-failure evidence refs and `event_failure_risk_vector` conditioning | M03 event-state consumes reviewed governance/model evidence; raw event acquisition does not become a symmetric trading-data source by default. |
| `AlphaConfidenceModel` | _(no trading-data source/feature)_ | `target_context_state`, `event_failure_risk_vector`, upstream context, realized outcomes/labels | Does not require new source acquisition, feature package, SQL view, or manifest contract in `trading-data`; labels belong outside inference features and are materialized only through reviewed deterministic evaluation contracts. |
| `PositionProjectionModel` | _(no trading-data source/feature)_ | final adjusted `alpha_confidence_vector`, costs, risk budget, current/pending position state | Projects target holding state and abstract target exposure outside `trading-data`; it does not produce buy/sell/hold or execution instructions. |
| `UnderlyingActionModel` | _(no trading-data source/feature)_ | `position_projection_vector`, upstream context, action-policy context | Offline underlying-action recommendation is model/control-plane work; no deterministic source-derived feature package is owned here. |
| `TargetStateVectorModel` option context | `trading_data.option_chain_state_source`, `trading_data.model_03_target_state_vector_feature_generation` | shared contract-level option-chain source/cache reduced into anonymous target-level option-chain state | `trading-data` keeps contract fields in the source/cache table only; M02 emits target option liquidity, IV pressure, skew, term-structure, and flow/activity state without contract identity or executable option terms. |
| `OptionExpressionModel` | `trading_data.option_chain_state_source`, `trading_data.model_05_option_expression_feature_generation` | shared contract-level option-chain source/cache and deterministic option-candidate feature payloads | `trading-data` prepares moneyness, spread/liquidity, IV, Greeks, and quality payloads from the shared option-chain rows; `trading-model` owns contract ranking and expression choice. |
| `OptionExpressionModel` replay/evaluation | `trading_data.model_05_option_expression_data_acquisition_contract_path` | selected option contract time series | Tracks the market path of selected contracts from entry through exit plus one hour; this is option-contract path data for replay/evaluation, not a broker execution table. |
| `M03 Event State` | `trading_data.model_03_event_state_data_acquisition`, `trading_data.model_03_event_state_feature_generation` | one-row-per-observed-event/evidence overview table plus deterministic event-overview feature payloads | Combines lagging evidence and prior-signal events while details remain behind URL/path references; canonical-event/dedup fields prevent derivative coverage from becoming duplicate alpha; `trading-model` builds M03 taxonomy/effect-model input from this feature surface plus reviewed context states/artifacts. |

## Implemented Model Input Sources

Each accepted model that needs new `trading-data` acquisition has a control-plane-facing data-acquisition or feature-generation table. These sources fetch/prepare external observations needed by the model; they are not the complete model-input or training-data universe.

M01 accepts `params.start` and `params.end`, reads the reviewed `model_01_background_context_etf_universe.csv` for ETF scope and bar grains, fetches Alpaca bars, and writes one combined SQL long table, `trading_data.model_01_market_regime_data_acquisition`. Its feature construction writes `trading_data.model_01_market_regime_feature_generation` and must keep market-context input frames separate. The accepted training/evaluation pairing is `1min -> 10min`, `10min -> 1h`, `1h -> 1D`, and `1D -> 1W`. Future outcomes for those horizons are labels/evaluation indicators, not inference features.

M02 feature construction reads cleaned M01 bar rows plus reviewed relative-strength combinations and writes `trading_data.model_02_sector_context_feature_generation`. It owns deterministic point-in-time evidence for broad sector-anchor behavior under market context: relative strength, normalized trend distance/slope/spread/alignment, volatility ratio, correlation, breadth, and dispersion. The reviewed M02 ETF universe is restricted to the 11 Select Sector SPDR anchors plus the `BKCH` crypto context-anchor exception; focused industry-chain and theme ETFs are outside the current M02 contract.

ETF holdings do not define the ordinary candidate universe. Live M02 target-state inputs use reviewed candidate symbols from the realtime total-symbol pool and target metadata, then attach the relevant broad sector-anchor context. Historical replay currently uses a fixed candidate universe seeded from the current realtime equity pool plus the reviewed BTC/ETH/SOL crypto spot candidate pool; this is stable replay scope, not point-in-time historical market-wide ranking evidence. Replay must not read the mutable realtime pool directly.

M02 has two target-state surfaces with different maturity.

Raw target-local observed inputs remain source-scoped: candidate-builder-supplied candidate rows plus reviewed local bar/liquidity artifacts are normalized into SQL table `trading_data.model_03_target_state_vector_data_acquisition`. Alpaca acquisition for these candidate-dependent rows is deferred until the manager supplies the candidate universe and bounded feed artifacts.

Target state-vector construction is feature-scoped: `trading-manager` issues a request with a reviewed window, anonymous candidate-universe reference, M01/M02 state references, and output target; `trading-data` builds deterministic market/sector/target/cross-state feature blocks and writes `trading_data.model_03_target_state_vector_feature_generation`. When listed options apply and `trading_data.option_chain_state_source` has point-in-time rows for a target, M02 reduces them into `target_option_chain_state` as target-level option liquidity, IV pressure, skew, term-structure, and flow/activity state. Targets marked as `crypto_spot` or `confirmed_no_listed_options` emit `target_option_capability_state` with structural no-option availability and omit chain-derived option state. Contract identity, strike, expiry, DTE, Greeks, premium, quote, and snapshot refs stay out of M02 model-facing state. `trading-model` consumes that surface to train/evaluate `TargetStateVectorModel` against market-only and market+sector baselines.

M03 event-state accepts `params.start`, `params.end`, focus sectors/symbols, and event overview rows, then writes SQL table `trading_data.model_03_event_state_data_acquisition`, one row per observed event/evidence row. It stores `canonical_event_id`, `dedup_status`, `source_priority`, `coverage_reason`, and `covered_by_event_id` so SEC/company/regulatory canonical events can cover derivative news without double-counting event presence or alpha factors. Full news, SEC, macro, abnormal-activity detector, browser/agent analysis, revision, and timeline details remain behind references. Earnings/guidance scouting rows are now materialized as `earnings_guidance` overview rows: Nasdaq/calendar artifacts are scheduled shells only, while SEC/company official artifacts are result/guidance evidence. Calendar and market-structure rows such as holidays, early closes, long weekends, option-expiry/triple-witching windows, and index rebalance windows are global event-pool observations until M03 event-effect review promotes a plausible relationship into the focused/watched event pool for systematic acquisition, offline M03 event-state candidate training, and M04 decision validation. Persistent-regime rows such as pandemic, tariff-war, geopolitical war/escalation, sanctions, banking-system stress, or policy crisis periods preserve point-in-time interval facts and may remain active/shadow-active without same-day news. `trading_data.model_03_event_state_feature_generation` turns accepted overview rows into deterministic source-only event-category, scope, dedup, source-priority, and quality payloads. `trading-model` builds `event_context_vector` by combining this point-in-time feature surface with event artifacts, upstream `market_context_state` / `sector_context_state` / `target_context_state` references, and reviewed scope/sensitivity metadata.

Historical and realtime/future event acquisition source priority is governed by `docs/23_event_source_registry.md`. Macro event observations use canonical Trading Economics storage rows as accepted source evidence; bounded TE recent/future refresh may append those rows, and M03 event-state materialization derives `macro_data` event overview rows from reviewed TE storage artifacts. Market-session observations such as holidays, weekends, early closes, long non-trading intervals, option expirations, triple-witching windows, and ETF/index rebalance windows enter M03 event-state materialization as `market_structure` context before attribution. Persistent regimes are promoted from repeated high-frequency news topics through agent review before becoming `persistent_event_regime` interval rows.

`trading_data.option_chain_state_source` accepts manager-supplied `params.underlying`, `params.snapshot_time`, optional `params.window_start` / `params.window_end`, and option-chain scope controls, calls the ThetaData option selection snapshot interface once, and writes one contract-level source/cache row per visible contract per returned minute. Historical training acquisition is prepared by the manager only for targets whose metadata leaves listed options applicable; crypto and confirmed no-listed-options targets do not prepare this source, but downstream M05 still emits explicit direct-underlying/no-option states. Provider policy caps remain `1d` while each task key carries the narrower 30-minute `window_start` / `window_end`. The resulting shared SQL rows serve M02 target-level reduction and M05 option-expression candidate preparation through `snapshot_time` range reuse.

`trading_data.model_05_option_expression_feature_generation` reads `option_chain_state_source` rows directly and turns accepted point-in-time snapshots into deterministic source-only option-candidate payloads for moneyness, spread/liquidity, IV, Greeks, and quality diagnostics.

`trading_data.model_05_option_expression_data_acquisition_contract_path` accepts `params.selected_contracts` from the option-expression handoff and writes selected option contract market data from entry time through exit time plus one hour. It emits market data only and must not produce execution instructions, order fields, PnL labels, or model outputs.

## Source-Backed Aggregations That Need Migration Review

### `stock_etf_exposure`

Integrated step: `src/data_source/m02_sector_context_data_acquisition/pipeline.py`

Status: retired from the current ordinary candidate and replay route.

Purpose: historical source-backed stock-to-ETF exposure evidence only. It must not define the ordinary equity candidate universe, the realtime total-symbol pool, M02 feature generation, or historical replay candidates. If revived, it needs a separately reviewed proxy/theme or exposure-evidence contract.

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
- Not a M02 core behavior-model input.
- Stock-level exposure features that combine source holdings with model scores require explicit boundary review: deterministic source-derived features may live in `trading-data`; model-derived scores belong in `trading-model`.

### `equity_abnormal_activity_event`

Source: `src/data_source/m03_event_state_data_acquisition/equity_abnormal_activity/`

Config: `src/data_source/m03_event_state_data_acquisition/equity_abnormal_activity/config.json`

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
- Must not duplicate ordinary `equity_bar`, `equity_liquidity_bar`, volatility, gap, volume, spread, trend, or target-state features that already feed M01-3 or the base trading-guidance path.
- Implemented first as a conservative detector over reviewed equity bar/liquidity evidence. Ordinary Alpaca bars are retained in SQL, not saved `equity_bar.csv`/`equity_bar.jsonl` payload files. Those inputs are provenance for a compact event token/residual evidence row, not permission to re-emit the same bar-derived fields as independent event alpha.
- Price-action tokens are detector evidence for M03 event-state governance; they are not a separate model layer, trading action, or production-calibrated label without reviewed historical evidence.
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

- `trading_data.option_chain_state_source` plus `trading_data.model_05_option_expression_feature_generation` are the option-expression input surfaces; they are not M04 decision `AlphaConfidenceModel` acquisition.
- SQL business tables keep `run_id`, `task_id`, and write audit timestamps in receipts/run metadata rather than business rows.
- ETF holdings freshness is conservative by default: explicit source/task `available_time` wins; otherwise holdings become visible at the next regular US session open after `as_of_date`.
- `equity_abnormal_activity_event` default standard is `equity_abnormal_activity_conservative`; production labels or promoted gates require reviewed historical calibration evidence before threshold changes are trusted.
- Optionability summary shape should be defined only when the model/control-plane contract needs a durable shared interface.
