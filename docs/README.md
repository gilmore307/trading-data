# Docs

This directory is the authoritative documentation spine for `trading-data`.

## Files

- `00_scope.md` — repository boundary, in-scope work, out-of-scope work, and owner intent.
- `01_context.md` — why the repository exists, related systems, environment assumptions, and dependencies.
- `02_layer_01_market_regime.md` — Layer 1 data workflow, source/feature boundary, and acceptance gates.
- `03_layer_02_sector_context.md` — Layer 2 data workflow, feature boundary, and acceptance gates.
- `80_task.md` — current task state, queued work, blockers, and recently accepted work.
- `81_decision.md` — ratified repository decisions.
- `82_memory.md` — durable local continuity that does not fit narrower docs.
- `90_data_organization.md` — guide for source-backed sources, outputs, and historical domain-label mapping.
- `91_data_feed.md` — guide for data-feed connectors, provider credentials, and API/token boundaries.
- `92_api_templates.md` — guide for applying `trading-manager/templates/data_tasks/` to API-specific feeds and control-plane-facing sources.
- `93_feed_availability.md` — inventory of verified feed availability and registered data-kind groups.
- `94_model_inputs.md` — mapping from `trading-data` source-backed outputs and derived products to model-layer data sources.
- `95_data_stack_closeout.md` — accepted closeout receipt for the current data-source/model-input design phase and remaining production-hardening scope.
- `96_production_hardening.md` — accepted live-call, retry/rate-limit, checkpoint/resume, manifest, ready-signal, and ThetaData runbook policy for work that does not require accumulated production data.

Layer workflow and acceptance live in the numbered layer files. Current model-input/data-source design is closed in `95_data_stack_closeout.md`; future changes should be scoped as production hardening, bug fixes, or explicitly accepted architecture revisions. Production hardening policy that can be defined before real production labels/data exists lives in `96_production_hardening.md`.

Do not place generated data, provider dumps, artifacts, notebooks, logs, credentials, or implementation outputs in this directory.
