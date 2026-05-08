# Docs

This directory is the documentation spine for `trading-data`.

## Files

- `00_scope.md` — repository purpose, scope, and boundary rules.
- `01_context.md` — why the repository exists and which systems it depends on.
- `02_layer_01_market_regime.md` — Layer 1 data workflow and acceptance gates.
- `03_layer_02_sector_context.md` — Layer 2 feature workflow and acceptance gates.
- `04_layer_03_target_state_vector.md` — Layer 3 target-state data workflow and gates.
- `05_layer_04_event_overlay.md` — Layer 4 event-overlay data boundary.
- `06_layer_05_alpha_confidence.md` — Layer 5 no-new-source/no-feature boundary.
- `07_layer_06_position_projection.md` — Layer 6 no-new-source/no-feature boundary.
- `08_layer_07_underlying_action.md` — Layer 7 no-new-source/no-feature boundary.
- `09_layer_08_option_expression.md` — Layer 8 option-expression data boundary.
- `80_task.md` — active queue and accepted work summary.
- `81_decision.md` — ratified decision history.
- `82_memory.md` — durable local notes that do not fit narrower docs.
- `90_data_organization.md` — feed/source/feature organization and output rules.
- `91_data_feed.md` — provider/feed boundaries, credentials, and live-call rules.
- `92_api_templates.md` — source/feed design order and template usage.
- `93_feed_availability.md` — provider/data-kind availability inventory.
- `94_model_inputs.md` — mapping from data outputs to model-layer consumers.
- `95_data_stack_closeout.md` — accepted local data-stack closeout.
- `96_production_hardening.md` — live-call, retry, checkpoint, manifest, ready-signal, and ThetaData hardening rules.

Current direct route:

```text
data_feed -> data_source -> data_feature -> SQL/artifact handoff
```

Keep generated data, provider dumps, artifacts, notebooks, logs, credentials, and runtime outputs out of this directory.
