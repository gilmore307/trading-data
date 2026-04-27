# trading-data

`trading-data` is the data upstream repository for the trading system.

It owns historical market and related data ingestion, normalization, validation, and data-output production for downstream trading repositories. It executes self-contained task key files from `trading-manager`; during development it writes cleaned outputs and receipts under ignored local files in `storage/`, and later it will move to durable storage targets once `trading-storage` contracts are accepted.

It does not own shared storage policy, strategy logic, model research, execution, dashboard rendering, secrets, credentials, notebooks, or generated data committed to Git.

## Top-Level Structure

```text
docs/        Required docs spine plus component-specific guides for data domains and data sources.
src/         Importable data-source, source-interface, and template-generator implementation packages.
tests/       First-party tests for data-source pipelines, interface probes, and generated templates.
storage/     Local development storage root plus committed storage-facing templates under `storage/templates/`.
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
  07_data_domains.md
  08_data_sources.md
  09_api_templates.md
```

## Input And Output

Input: self-contained historical data task key files from `trading-manager` once the task-key contract is accepted.

Development output: cleaned local files and task completion receipts under `storage/` (ignored by Git).

Future durable output: storage-backed SQL/artifact outputs plus manifests and ready signals once cross-repository contracts are accepted.

`trading-data` fetches and cleans historical data; realtime feeds belong to `trading-execution`, and generated datasets must not be stored in Git.

## Data Domains

`trading-data` currently plans three data domains by research purpose:

- market board data / 盘面数据;
- instrument data / 标的数据;
- option data / 期权数据.

See `docs/07_data_domains.md`. API-specific bundle design guidance is in `docs/09_api_templates.md`.

## Platform Dependencies

- `trading-main` owns global contracts, registry, shared helpers, and templates.
- `trading-storage` owns durable storage layout, retention, archive, backup, and restore rules.
- `trading-manager` owns scheduling, request generation, lifecycle, retries, and promotion decisions.

Any new global helper, template, shared field, status, type, or reusable vocabulary discovered while developing `trading-data` must be routed back to `trading-main` for documentation and registry review before other repositories depend on it.
