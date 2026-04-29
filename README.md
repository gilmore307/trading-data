# trading-source

`trading-source` is the external/source-backed observed-data repository for the trading system.

It owns historical market, options, issuer, filing, news, calendar, and related provider data acquisition, cleaning, validation, and publication for downstream repositories. It executes self-contained task key files from `trading-manager`; legacy source pipelines may still create ignored local files under runtime `storage/`, while accepted SQL-only source outputs write directly to reviewed SQL tables.

It does not own shared storage policy, derived labels/samples/signals/outcomes, strategy/backtest generation, model research, execution, dashboard rendering, secrets, credentials, notebooks, or generated data committed to Git.

## Top-Level Structure

```text
docs/        Required docs spine plus component-specific guides for data organization and data sources.
src/         Importable data-feed, feed-interface, data-source, storage, and probe implementation packages.
tests/       First-party tests for data-feed pipelines, interface probes, storage, and sources.
```

Executable CLIs are package entrypoints that call `src/`. If future operational wrappers are needed, place them under `scripts/`; `src/` must not import `scripts/`.

## Docs Set

```text
docs/
  00_scope.md
  01_context.md
  02_workflow.md
  03_acceptance.md
  04_task.md
  05_decision.md
  06_memory.md
  07_data_organization.md
  08_data_feed.md
  09_api_templates.md
  10_feed_availability.md
  11_model_inputs.md
```

## Input And Output

Input: self-contained historical data task key files from `trading-manager` once the task-key contract is accepted.

Development output: local SQL databases and, for legacy source pipelines, inspected local files and task completion receipts under runtime-created `storage/` (ignored by Git).

Durable output: storage-backed SQL/artifact outputs plus manifests and ready signals as cross-repository contracts are accepted.

`trading-source` fetches and cleans historical external observations; realtime feeds belong to `trading-execution`, and internally generated datasets belong to `trading-derived` rather than this repository.

## Data Organization

`trading-source` now organizes work around provider/feed adapters, source-backed manager-facing sources, and accepted SQL outputs. The old market-board / instrument / option domain labels remain historical planning language, not the primary runtime or docs boundary.

See `docs/07_data_organization.md`. API-specific source design guidance is in `docs/09_api_templates.md`; model-layer mapping is in `docs/11_model_inputs.md`.

## Platform Dependencies

- `trading-main` owns global contracts, registry, shared helpers, and templates.
- `trading-storage` owns durable storage layout, retention, archive, backup, and restore rules.
- `trading-manager` owns scheduling, request generation, lifecycle, retries, and promotion decisions.

Any new global helper, template, shared field, status, type, or reusable vocabulary discovered while developing `trading-source` must be routed back to `trading-main` for documentation and registry review before other repositories depend on it.
