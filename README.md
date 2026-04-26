# trading-data

`trading-data` is the data upstream repository for the trading system.

It owns market and related data ingestion, normalization, validation, and data-output production for downstream trading repositories. It produces data artifacts, manifests, and ready signals that are consumed through shared contracts defined in `trading-main` and persistent layout rules owned by `trading-storage`.

It does not own shared storage policy, strategy logic, model research, execution, dashboard rendering, secrets, credentials, notebooks, or generated data committed to Git.

## Top-Level Structure

```text
docs/        Repository scope, context, workflow, acceptance, task, decisions, and local memory.
```

Source, tests, and package layout are intentionally not created yet. They should be added only after the data contracts, provider choices, and storage handoff expectations are explicit.

## Docs Spine

```text
docs/
  00_scope.md
  01_context.md
  02_workflow.md
  03_acceptance.md
  04_task.md
  05_decision.md
  06_memory.md
```

## Platform Dependencies

- `trading-main` owns global contracts, registry, shared helpers, and templates.
- `trading-storage` owns durable storage layout, retention, archive, backup, and restore rules.
- `trading-manager` owns scheduling, request generation, lifecycle, retries, and promotion decisions.

Any new global helper, template, shared field, status, type, or reusable vocabulary discovered while developing `trading-data` must be routed back to `trading-main` for documentation and registry review before other repositories depend on it.
