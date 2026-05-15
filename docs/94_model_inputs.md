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
| `EventOverlayModel` | `source_04_event_overlay`, `feature_04_event_overlay` | one-row-per-observed-event/evidence overview table plus deterministic event-overview feature payloads | Combines lagging evidence and prior-signal events while details remain behind URL/path references; canonical-event/dedup fields prevent derivative coverage from becoming duplicate alpha; `trading-model` builds `event_context_vector` from this feature surface plus reviewed context states/artifacts. |
| `AlphaConfidenceModel` | _(no trading-data source/feature)_ | `target_context_state`, `event_context_vector`, upstream context, realized outcomes/labels | Does not require new source acquisition, feature package, SQL view, or manifest contract in `trading-data`; labels belong outside inference features and are materialized only through reviewed deterministic evaluation contracts. |
| `PositionProjectionModel` | _(no trading-data source/feature)_ | final adjusted `alpha_confidence_vector`, costs, risk budget, current/pending position state | Projects target holding state and abstract target exposure outside `trading-data`; it does not produce buy/sell/hold or execution instructions. |
| `UnderlyingActionModel` | _(no trading-data source/feature)_ | `position_projection_vector`, upstream context, action-policy context | Offline underlying-action recommendation is model/control-plane work; no deterministic source-derived feature package is owned here. |
| `OptionExpressionModel` | `source_05_option_expression`, `feature_08_option_expression` | contract-level option-chain snapshots and deterministic option-candidate feature payloads at entry/exit decision points | `trading-data` prepares moneyness, spread/liquidity, IV, Greeks, and quality payloads; `trading-model` owns contract ranking and expression choice. |
| `OptionExpressionModel` replay/evaluation | `source_06_position_execution` | selected-contract option time series | Tracks the market path of selected contracts from entry through exit plus one hour; this is a data source for option-expression replay/evaluation, not a model-output layer. |

## Implemented Model Input Sources

Each accepted model layer that needs new `trading-data` acquisition has a control-plane-facing source-backed source under `src/data_source/source_NN_<layer_slug>/`. These sources fetch/prepare external observations needed by the layer; they are not the complete model-input or training-data universe.

Layer 1 accepts `params.start` and `params.end`, reads the reviewed `layer_01_02_market_context_etf_universe.csv` for ETF scope and bar grains, fetches Alpaca bars, and writes one combined SQL long table, `source_01_market_regime`.

Layer 2 feature construction reads cleaned Layer 1 bar rows plus reviewed relative-strength combinations and writes `feature_02_sector_context`. It owns deterministic point-in-time evidence for sector/industry behavior under market context: relative strength, normalized trend distance/slope/spread/alignment, volatility ratio, correlation, breadth, and dispersion. It does not consume ETF holdings or `stock_etf_exposure` as core behavior-model inputs.

The downstream target-candidate preparation boundary accepts `params.start` and `params.end`, reads the reviewed `layer_01_02_market_context_etf_universe.csv` for ETF scope/issuer/exposure labels, keeps only `universe_type = sector_observation_etf` for holdings analysis, collects ETF holdings snapshots, filters them to US-listed equity constituents only, and writes SQL table `source_02_target_candidate_holdings`. Its semantic owner is the anonymous target candidate builder / Layer 3 input-preparation boundary after Layer 2 has selected/prioritized sector baskets.

Layer 3 has two target-state surfaces with different maturity.

Raw target-local observed inputs remain source-scoped: candidate-builder-supplied `params.start`, `params.end`, and `params.symbols` default to 1Min, fetch Alpaca bars plus transient trade/quote liquidity inputs, and should write SQL table `source_03_target_state`.

Target state-vector construction is feature-scoped: `trading-manager` issues a request with a reviewed window, anonymous candidate-universe reference, Layer 1/2 state references, and output target; `trading-data` builds deterministic market/sector/target/cross-state feature blocks and writes `feature_03_target_state_vector`. `trading-model` consumes that surface to train/evaluate `TargetStateVectorModel` against market-only and market+sector baselines.

Layer 4 accepts `params.start`, `params.end`, focus sectors/symbols, and event overview rows, then writes SQL table `source_04_event_overlay`, one row per observed event/evidence row. It stores `canonical_event_id`, `dedup_status`, `source_priority`, `coverage_reason`, and `covered_by_event_id` so SEC/company/regulatory canonical events can cover derivative news without double-counting event presence or alpha factors. Full news, SEC, macro, abnormal-activity detector, browser/agent analysis, revision, and timeline details remain behind references. `feature_04_event_overlay` turns accepted overview rows into deterministic source-only event-category, scope, dedup, source-priority, and quality payloads. `trading-model` builds `event_context_vector` by combining this point-in-time feature surface with event artifacts, upstream `market_context_state` / `sector_context_state` / `target_context_state` references, and reviewed scope/sensitivity metadata.

`source_05_option_expression` accepts manager-supplied `params.underlying`, `params.snapshot_time`, and optional `params.snapshot_type` (`entry`/`exit`, default `entry`), calls the ThetaData option selection snapshot interface, and writes one row per visible option contract per snapshot. `snapshot_time` is the point-in-time clock; quote/IV/Greeks provider row timestamps are intentionally omitted from the business table. `feature_08_option_expression` turns accepted snapshot rows into deterministic source-only option-candidate payloads for moneyness, spread/liquidity, IV, Greeks, and quality diagnostics. Despite the `source_05_` prefix, this is an option-expression source for the downstream `OptionExpressionModel`, not the model Layer 5 `AlphaConfidenceModel`.

`source_06_position_execution` accepts `params.selected_contracts` from the option-expression handoff and writes selected option contract market data from entry time through exit time plus one hour. It emits market data only and must not produce execution instructions, order fields, PnL labels, or model outputs.

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

Source: `src/data_source/source_04_event_overlay/equity_abnormal_activity/`

Config: `src/data_source/source_04_event_overlay/equity_abnormal_activity/config.json`

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
- Implemented first as a conservative detector over saved `equity_bar.csv`, optional benchmark bars, and optional `equity_liquidity_bar.csv` inputs. Those inputs are provenance for a compact event token/residual evidence row, not permission to re-emit the same bar-derived fields as independent event alpha.
- Price-action tokens are detector evidence for Layer 8 event-risk governance; they are not a separate model layer, trading action, or production-calibrated label without reviewed historical evidence.
- If this becomes a generated signal, candidate decision, or label rather than source evidence, move that behavior out of `trading-data` and into the owning model/evaluation boundary.

### `event_activity_bridge` evidence refs

`event_activity_bridge` is model-owned, but `trading-data` may provide point-in-time evidence refs that support it:

- event evidence refs: news, SEC/company disclosure, macro/calendar, official data, or hard-to-standardize narrative artifacts;
- price activity refs: compact residual/price-action evidence, not duplicated bar features;
- liquidity activity refs: spread/depth/quote-quality/halt-pause evidence;
- option activity refs: IV/skew/term-structure/volume/OI/liquidity evidence when not already consumed as base option-expression inputs;
- prediction-market activity refs: future Polymarket-style odds/volume/liquidity refs, when that source boundary is accepted.

The bridge is useful when raw news is too ambiguous to standardize confidently but market/odds activity provides stable lead-lag or confirmation/divergence evidence. `trading-data` preserves refs and clocks; `trading-model` owns bridge scoring and interpretation.

## Current Guardrails

- `source_05_option_expression` is source-number 05 for option-expression input; it is not model Layer 5 `AlphaConfidenceModel` acquisition.
- SQL business tables keep `run_id`, `task_id`, and write audit timestamps in receipts/run metadata rather than business rows.
- ETF holdings freshness is conservative by default: explicit source/task `available_time` wins; otherwise holdings become visible at the next regular US session open after `as_of_date`.
- `equity_abnormal_activity_event` default standard is `equity_abnormal_activity_conservative`; production labels or promoted gates require reviewed historical calibration evidence before threshold changes are trusted.
- Optionability summary shape should be defined only when the model/control-plane contract needs a durable shared interface.
