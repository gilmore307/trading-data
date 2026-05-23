# Layer 10 — Event Risk Governor Data Boundary

<!-- ACTIVE_LAYER_REVISION -->
Status: active architecture revision. Layer 10 owns `EventRiskGovernor / EventIntelligenceOverlay` qualitative event attribution, reviewed-pool governance, and event-risk intervention. `trading-data` owns point-in-time event evidence indexes, deterministic event-overview features, and attribution evidence refs, not event interpretation, attribution decisions, risk policy, execution, or broker mutation.

Current physical source/feature names are `source_10_event_risk_governor` and `feature_10_event_risk_governor`. Event feeds must preserve point-in-time availability, row coverage, dedup/canonical metadata, and evidence refs for `event_interpretation` and event-risk governor use.
<!-- /ACTIVE_LAYER_REVISION -->


`trading-data` owns the point-in-time event evidence index for Layer 10. Model-side event interpretation, event vectors, labels, training, evaluation, and promotion belong to `trading-model`.

## Owned artifacts

```text
trading_data.source_10_event_risk_governor
trading_data.feature_10_event_risk_governor
```

Nested event-overlay data-source helpers may produce source evidence before it is written into the overview table, for example:

```text
src/data_source/source_10_event_risk_governor/equity_abnormal_activity/
```

`price_action` is an accepted Layer 10 event category for detector-visible board/tape behavior. In V1 it is represented as source-detector evidence, not as a new model layer. Canonical event-type tokens include `false_breakout`, `false_breakdown`, `liquidity_sweep_high`, `liquidity_sweep_low`, `bull_trap`, and `bear_trap`.

## Boundary

Layer 10 data is an event index plus deterministic event-overview features, not the full `event_risk_intervention / event_context_vector` and not event-failure attribution.

`source_10_event_risk_governor` stores one overview row per observed event/evidence row with point-in-time availability and deduplication fields. Full article text, SEC filing contents, browser/agent analysis, abnormal-activity details, revision history, and event artifacts stay behind references.

`feature_10_event_risk_governor` derives source-only categorical, deduplication, source-priority, scope, and quality payloads from accepted overview rows. It is the deterministic feature handoff for model input preparation.

`trading-model` builds `event_risk_intervention / event_context_vector` from the feature rows plus referenced artifacts and upstream context states.

Layer 10's post-failure attribution route adds one data requirement: event rows and referenced artifacts must remain joinable to model failure/residual windows by point-in-time clocks. `trading-data` preserves event availability, source refs, activity windows, and compact detector evidence; `trading-model` decides whether those events explain a failure, computes `realized_impact_scope_label`, builds attribution labels, and proposes Layer 4 promotion packets.

Layer 10 is the qualitative event-impact and attribution layer, but qualitative decisions belong to `trading-model` and review. `trading-data` supports that route by preserving the evidence needed to test attribution, including co-event grouping and confounder controls when available.

## Input boundary

Accepted event rows may include:

- macro calendar/data-release events;
- macro, sector, symbol, or broad-market news events;
- SEC/company/regulatory filings or disclosures;
- option abnormal-activity evidence, when not duplicating option-expression inputs already consumed by the base path;
- equity/ETF residual abnormal-activity evidence, only as trigger/provenance/residual evidence rather than duplicated bar/liquidity features;
- price-action detector evidence such as false breakouts, failed breakdowns, liquidity sweeps, bull traps, or bear traps;
- source references, web URLs, SEC paths, or internal artifact paths.

Required semantics:

- `event_time` is when the event occurred or became effective.
- `available_time` is when the event evidence may be used by model logic.
- `canonical_event_id`, `dedup_status`, `source_priority`, `coverage_reason`, and `covered_by_event_id` prevent derivative coverage from becoming duplicate alpha.
- Event evidence must preserve lifecycle clocks when the source provides or implies them: awareness, scheduled, published, available, interpretation, resolution, and reaction/evaluation windows.
- Scheduled-known events and unscheduled surprise events must not be collapsed into the same raw timing shape. Earnings and macro-calendar shells may be visible before results; sudden news is only visible after the first credible source.

Co-event/confounder evidence should be preserved when available:

```text
co_event_group_id
dominant_event_candidate_ref
confounder_event_ref
co_event_window
co_event_relation_type
source_scope_hint
```

These fields or refs are evidence only. `trading-data` does not decide whether a candidate event is dominant, spurious, incrementally explanatory, or eligible for Layer 4 supervision.

Trading-calendar and market-structure windows are attribution evidence when failures occur around non-trading intervals, expiry, or rebalance windows. `trading-data` should preserve calendar facts such as closure type, non-trading interval length, next market open, holiday name, early close, pre-holiday session flags, triple-witching/option-expiry flags, and index rebalance flags when available. `trading-model` decides whether the date has enough incremental explanatory value to supervise future Layer 4 risk conditioning.

Calendar and market-structure rows live first in the global event observation pool. The row's job is to make the date, lifecycle clocks, and source/provenance knowable; it must not assert that the date caused a failure. When Layer 10 later accepts a relationship after attribution and review, the accepted family/mechanism enters the watched event pool for future Layer 4 training.

Accepted lifecycle classes for downstream interpretation:

```text
scheduled_known_outcome_later
unscheduled_surprise
scheduled_recurring_data_release
multi_stage_developing_event
unknown
```

`trading-data` does not interpret final risk impact, but it must not destroy source timing needed to distinguish these classes. If a physical table does not yet have dedicated lifecycle columns, source evidence artifacts must retain the clocks/fields behind refs until a reviewed schema migration adds first-class columns.

## Event-activity bridge evidence

`trading-data` may provide evidence refs for the model-owned `event_activity_bridge` contract. The bridge lets hard-to-standardize news be represented through observable activity relationships instead of overfitting fragile narrative categories.

Accepted bridge evidence legs include:

```text
event_evidence_ref
price_activity_ref
liquidity_activity_ref
option_activity_ref
prediction_market_activity_ref
```

Startup abnormality scope is limited to compact point-in-time detector refs for: false breakout/breakdown, liquidity sweep high/low, bull/bear trap, residual board/tape disturbance after upstream conditioning, spread/depth/quote-quality/halt or one-sided liquidity disruption, and reviewed option IV/skew/term-structure/volume/OI/liquidity disturbance. Raw bar, target-state, liquidity-feature, option-expression, Layer 10 event-risk guidance, strategy-failure, and post-event realized-label fields are excluded from activity evidence unless a later reviewed artifact proves residual/non-overlap status.

`trading-data` owns source refs, windows, availability clocks, and compact detector evidence. It does not decide final bridge scores, prediction-market probabilities, event-risk interventions, or trading actions.

Bridge evidence must preserve a non-overlap audit trail. Price, liquidity, and option activity refs are eligible for model-side scoring only when the artifact can show that the activity leg is not already represented in upstream market/sector/target-state features, liquidity features, option-expression inputs, or Layer 9 trading-guidance payloads for the same decision context. If overlap is unknown, `trading-data` should keep the ref as provenance/review evidence and let `trading-model` mark the bridge `review_required_overlap_unknown` rather than treating it as incremental event evidence.

Event-family scouting adds one data requirement: raw provider rows must preserve enough source metadata for `trading-model` to create reviewed `event_family_scouting_packet` evidence. For news this means source name, provider id, headline/summary or source artifact ref, URL/ref, published/updated times, available time when known, symbol/entity tags, and dedup/canonical refs when available. `trading-data` should not collapse raw news into a final family label or event-risk conclusion; it may provide deterministic source fields and evidence refs.

For `earnings_guidance_event_family`, `trading-data` source artifacts must distinguish scheduling shells from result artifacts. Nasdaq earnings-calendar style rows may support `scheduled_time` / `event_awareness_time` only; SEC EDGAR/company official artifacts or an accepted company-IR route must supply result/guidance facts. Alpaca/GDELT news remains discovery or narrative-residual evidence unless linked to a canonical result artifact.

Before bridge evidence can be used for model-layer promotion, `trading-data` must preserve separate windows for:

```text
activity_detection_window
event_availability_window
forward_label_window
```

This prevents price-derived abnormality from being validated against the same price interval that created it. Required future labels include forward return, drawdown, reversal, volatility expansion, gap/jump, and path asymmetry.

## Stage flow

```text
trading-manager event/source request
  -> data_feed evidence and/or source-provided event rows
  -> source_10_event_risk_governor
  -> feature_10_event_risk_governor
  -> trading-model Layer 10 event-failure attribution or reviewed-pool governance
  -> evaluation/promotion review outside trading-data
  -> accepted future Layer 4 event_strategy_failure_gate / event-observation scope rules
```

## Non-ownership

`trading-data` does not own:

- final event impact scores;
- event-context vector modeling;
- event-failure attribution decisions;
- `realized_impact_scope_label` evaluation labels;
- co-event/confounder attribution decisions;
- Layer 4 event-family promotion packets;
- alpha labels;
- buy/sell/hold decisions;
- position sizing;
- option contract choice;
- production promotion decisions.

## Acceptance notes

Layer 10 data changes are acceptable when they:

- preserve point-in-time availability;
- keep source evidence separate from model labels and alpha scores;
- use canonical/dedup fields for represented duplicate coverage;
- keep full bulky evidence behind references unless a reviewed artifact contract says otherwise;
- route reusable names through `trading-manager` before cross-repository dependence.
## Cross-sectional proof-study data requirement

A single symbol can debug the activity-price relationship workflow, but it cannot prove the relationship. `trading-data` evidence for the proof gate must support samples across:

```text
size_bucket
sector_theme_bucket
event_family
activity_class
bridge_relation_type
```

Source outputs must preserve market/sector/theme controls and avoid mixing detector windows with forward labels.

## Option-direction evidence requirement

For option activity, `trading-data` must preserve direction evidence separately from generic activity evidence. Minimum retained evidence should include:

```text
option_right
trade_side_or_aggressor_side
ask_touch_ratio
bid_touch_ratio
sweep_or_block_context
trade_size
trade_notional
window_volume
open_interest_change
opening_or_closing_context
iv_change
skew_direction
term_structure_direction
direction_confidence
```

Ask-side call activity may be bullish and ask-side put activity may be bearish, but this is a hypothesis for model evaluation, not a guaranteed fact. Raw call/put volume without side/aggressor/opening context should usually map to `unknown_direction_activity` or `review_required`.
