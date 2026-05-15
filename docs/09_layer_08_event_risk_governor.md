# Layer 08 — Event Risk Governor Data Boundary

<!-- ACTIVE_LAYER_REVISION -->
Status: active architecture revision. Layer 8 owns `EventRiskGovernor / EventIntelligenceOverlay` event intelligence / event-risk intervention. `trading-data` owns point-in-time event evidence indexes and deterministic event-overview features, not event interpretation, risk policy, execution, or broker mutation.

Current physical source/feature names remain `source_04_event_overlay` and `feature_04_event_overlay` until a dedicated implementation migration renames surfaces. Event feeds must preserve point-in-time availability, row coverage, dedup/canonical metadata, and evidence refs for `event_interpretation_v1` and event-risk governor use.
<!-- /ACTIVE_LAYER_REVISION -->


`trading-data` owns the point-in-time event evidence index for Layer 8. Model-side event interpretation, event vectors, labels, training, evaluation, and promotion belong to `trading-model`.

## Owned artifacts

```text
trading_data.source_04_event_overlay
trading_data.feature_04_event_overlay
```

Nested event-overlay data-source helpers may produce source evidence before it is written into the overview table, for example:

```text
src/data_source/source_04_event_overlay/equity_abnormal_activity/
```

`price_action` is an accepted Layer 8 event category for detector-visible board/tape behavior. In V1 it is represented as source-detector evidence, not as a new model layer. Canonical event-type tokens include `false_breakout`, `false_breakdown`, `liquidity_sweep_high`, `liquidity_sweep_low`, `bull_trap`, and `bear_trap`.

## Boundary

Layer 8 data is an event index plus deterministic event-overview features, not the full `event_risk_intervention / event_context_vector`.

`source_04_event_overlay` stores one overview row per observed event/evidence row with point-in-time availability and deduplication fields. Full article text, SEC filing contents, browser/agent analysis, abnormal-activity details, revision history, and event artifacts stay behind references.

`feature_04_event_overlay` derives source-only categorical, deduplication, source-priority, scope, and quality payloads from accepted overview rows. It is the deterministic feature handoff for model input preparation.

`trading-model` builds `event_risk_intervention / event_context_vector` from the feature rows plus referenced artifacts and upstream context states.

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

Accepted lifecycle classes for downstream interpretation:

```text
scheduled_known_outcome_later
unscheduled_surprise
scheduled_recurring_data_release
multi_stage_developing_event
unknown
```

`trading-data` does not interpret final risk impact, but it must not destroy source timing needed to distinguish these classes. If a physical table does not yet have dedicated lifecycle columns, source evidence artifacts must retain the clocks/fields behind refs until a reviewed schema migration adds first-class columns.

## Stage flow

```text
trading-manager event/source request
  -> data_feed evidence and/or source-provided event rows
  -> source_04_event_overlay
  -> feature_04_event_overlay
  -> trading-model EventRiskGovernor / EventOverlayModel event_risk_intervention / event_context_vector construction
  -> evaluation/promotion review outside trading-data
```

## Non-ownership

`trading-data` does not own:

- final event impact scores;
- event-context vector modeling;
- alpha labels;
- buy/sell/hold decisions;
- position sizing;
- option contract choice;
- production promotion decisions.

## Acceptance notes

Layer 8 data changes are acceptable when they:

- preserve point-in-time availability;
- keep source evidence separate from model labels and alpha scores;
- use canonical/dedup fields for represented duplicate coverage;
- keep full bulky evidence behind references unless a reviewed artifact contract says otherwise;
- route reusable names through `trading-manager` before cross-repository dependence.