# Scope

## Purpose

`trading-data` is the trading system's data-production component.

It turns approved historical data requests into normalized source outputs, deterministic feature outputs, and handoff evidence for downstream repositories. Its direct route is:

```text
provider/API/web/file -> data_feed -> data_source -> data_feature -> SQL/artifact handoff
```

The repository exists so data acquisition and normalization are explicit, testable, reproducible, and separate from modeling, strategy, execution, dashboard, and global storage concerns.

## In Scope

- Acquire historical market, option, issuer, filing, news, calendar, macro, and related provider/source data.
- Normalize provider responses into reviewed feed/source shapes.
- Validate schema, timestamps, market calendars, completeness, rate-limit behavior, and provider quirks.
- Execute manager-issued task/request files for historical data runs.
- Produce accepted SQL source tables, feature tables, final cleaned artifacts, run receipts, and sanitized development evidence.
- Keep `src/data_feed/` focused on provider/API/web/file access and feed-level normalization.
- Keep `src/data_source/` focused on manager-facing source orchestration and model-input source outputs.
- Keep `src/data_feature/` focused on deterministic feature construction from accepted source outputs.
- Keep default tests fixture-safe and live calls explicitly guarded.
- Record provider limitations, quotas, quality caveats, and source-of-truth rules.

## Out of Scope

- Global request, artifact, manifest, ready-signal, storage layout, retention, backup, archive, or restore policy.
- Model training, labels, evaluation, promotion, market-state discovery, strategy research, or backtests.
- Live/paper execution, broker mutation, order routing, or execution-time streaming data.
- Dashboard frontend/backend work.
- Production scheduling, approvals, retries, lifecycle routing, or task generation.
- Committing generated datasets, raw provider dumps, logs, notebooks, credentials, or secrets.
- General data-platform work unrelated to the trading system.

## Boundary Rules

- `trading-data` owns historical feed acquisition, model-scoped source production, deterministic feature production, and point-in-time data visibility.
- `trading-manager` owns shared names, registry rows, request/task contracts, scheduling, retries, approvals, and promotion control.
- `trading-storage` owns durable layout, manifests, artifact references, ready signals, retention, backup, and restore.
- `trading-model` owns labels, training, evaluation, and promotion decisions.
- Generated data and provider responses are runtime artifacts, not source files.
- Secrets must stay outside the repository and be referenced only by approved aliases.
- Source-backed aggregations may be emitted by `data_source`; raw provider access belongs in `data_feed`.
- Data features emitted here must be market/source based; strategy returns or execution outcomes must not feed upstream data production.

## Rejection Signals

Reject or re-scope a request if it asks `trading-data` to:

- implement model, strategy, execution, or dashboard logic;
- commit generated data, raw dumps, logs, notebooks, or credentials;
- define shared field/status/type names without registry review;
- bypass `trading-storage` for durable layout policy;
- use profitability or strategy performance as upstream source data;
- become a one-off script pile without tests, contracts, and acceptance evidence.
