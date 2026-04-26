# Docs

This directory is the authoritative documentation set for `trading-data`: the required docs spine plus optional component-specific guides.

## Files

- `00_scope.md` — repository boundary, in-scope work, out-of-scope work, and owner intent.
- `01_context.md` — why the repository exists, related systems, environment assumptions, and dependencies.
- `02_workflow.md` — data workflow, handoffs, and operating sequence.
- `03_acceptance.md` — acceptance gates, verification commands, evidence requirements, and rejection reasons.
- `04_task.md` — current task state, queued work, blockers, and recently accepted work.
- `05_decision.md` — ratified repository decisions.
- `06_memory.md` — durable local continuity that does not fit narrower docs.
- `07_data_domains.md` — optional guide for the three data domains: market board, instrument, and option data.
- `08_data_sources.md` — optional guide for data-source connectors, provider credentials, and API/token boundaries.
- `09_api_templates.md` — optional guide for applying `trading-main/templates/data_tasks/` to API-specific bundles.
- `10_source_availability.md` — optional inventory of verified source availability and registered data-kind groups.

Optional docs are allowed when they have a clear component-specific boundary and do not duplicate the required spine. Do not place generated data, notebooks, logs, credentials, or implementation artifacts in this directory.
