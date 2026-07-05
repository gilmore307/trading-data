# M03 Event State Data Boundary

`trading-data` owns the point-in-time evidence surface that lets M03 build an event distribution operator (`A3`). It does not own event interpretation, event-effect-model training, probability-surface construction, trading decisions, or component risk controls.

## Owned Artifacts

```text
trading_data.model_03_event_state_data_acquisition
trading_data.model_03_event_state_feature_generation
src/data_source/m03_event_state_data_acquisition/
src/data_feature/m03_event_state_feature_generation/
```

Nested helpers such as `src/data_source/m03_event_state_data_acquisition/equity_abnormal_activity/` may create compact detector evidence, but they are evidence producers inside the M03 event-state data surface, not standalone model layers.

## Boundary

M03 data rows preserve event evidence:

- point-in-time clocks: `event_time`, `available_time`, and source-derived lifecycle fields when present;
- identity and dedup fields: `event_id`, `canonical_event_id`, `dedup_status`, `covered_by_event_id`;
- source priority and provenance: `source_name`, `source_priority`, `reference_type`, `reference`, `source_artifact_path`;
- source-side category and scope hints: macro, sector, symbol, market-structure, option activity, equity abnormal activity, and price-action detector evidence.

M03 data rows must not assert:

- semantic event direction;
- final `event_effect_model`;
- alpha labels;
- mean/mode/contribution shifts;
- no-trade, cap, reduce, flatten, or broker/execution actions.

Those decisions belong to `trading-model` M03/M04 or execution components. Component-owned event-risk control may consume M03/M04/M05 outputs, but it is not a model output and is not produced by `trading-data`.

## Flow

```text
raw provider/feed artifact
-> point-in-time event evidence row / artifact ref
-> model_03_event_state_data_acquisition
-> model_03_event_state_feature_generation
-> trading-model M03 taxonomy/event_effect_model input
-> M04 thesis_distribution_surface
-> M05 expression_probability_surface
```

The source package writes one overview row per event/evidence row. Full article text, filing contents, browser/agent analysis, abnormal-activity details, revision history, and raw provider payloads stay behind references.

The feature package derives deterministic source-only payloads for M03 input preparation. It may encode category, scope, dedup, source priority, row quality, and PIT availability features. It must not create labels, score market impact, or decide whether an event explains a failure.

## Post-Replay Evidence

Replay attribution starts with model-side failure-scope triage. `trading-data` supports that route by keeping event evidence joinable to decision and label windows:

```text
failure window / residual context
-> market, sector, theme, peer, and target-local event evidence refs
-> co-event and confounder refs when available
-> model-side M03 event-effect-model review
```

The triage result may change acquisition order, budgets, and source weighting. It must not erase lower-scope evidence that may be needed for confounder checks.

## Non-Ownership

`trading-data` does not own:

- event taxonomy promotion;
- event-family effect-model validation;
- final event impact scores;
- event attribution decisions;
- realized impact labels;
- trade eligibility;
- position sizing;
- option contract choice;
- broker/order/account mutation.

## Acceptance

M03 event-state data changes are acceptable when they preserve PIT availability, keep source evidence separate from model labels and trade controls, expose compact provenance for replay joins, and keep source packages aligned with the `model_03_event_state_*` SQL table contracts.
