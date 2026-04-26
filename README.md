# trading-data

`trading-data` is the data upstream repository for the trading system.

It owns historical market and related data ingestion, normalization, validation, and data-output production for downstream trading repositories. It executes self-contained task key files from `trading-manager`, writes cleaned outputs to storage SQL targets once contracts are accepted, and produces completion evidence through shared contracts defined in `trading-main` and persistent layout rules owned by `trading-storage`.

It does not own shared storage policy, strategy logic, model research, execution, dashboard rendering, secrets, credentials, notebooks, or generated data committed to Git.

## Top-Level Structure

```text
docs/        Required docs spine plus component-specific guides for data domains and data sources.
```

Source, tests, and package layout are intentionally not created yet. They should be added only after the data contracts, provider choices, and storage handoff expectations are explicit.

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
```

## Input And Output

Input: self-contained historical data task key files from `trading-manager` once the task-key contract is accepted.

Output: cleaned storage SQL outputs plus task completion receipts, with manifests and ready signals once cross-repository contracts are accepted.

`trading-data` fetches and cleans historical data; realtime feeds belong to `trading-execution`, and generated datasets must not be stored in Git.

## Data Domains

`trading-data` currently plans three data domains by research purpose:

- market board data / 盘面数据;
- instrument data / 标的数据;
- option data / 期权数据.

See `docs/07_data_domains.md`.

## Platform Dependencies

- `trading-main` owns global contracts, registry, shared helpers, and templates.
- `trading-storage` owns durable storage layout, retention, archive, backup, and restore rules.
- `trading-manager` owns scheduling, request generation, lifecycle, retries, and promotion decisions.

Any new global helper, template, shared field, status, type, or reusable vocabulary discovered while developing `trading-data` must be routed back to `trading-main` for documentation and registry review before other repositories depend on it.
