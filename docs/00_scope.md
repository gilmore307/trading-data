# Scope

## Purpose

`trading-data` is the data upstream repository for the trading system.

It owns the component-level work required to acquire, normalize, validate, and publish market and related data for downstream trading repositories. It turns approved data requests into data artifacts, manifests, and ready signals.

This repository exists to make data production explicit, testable, and reusable without mixing data ingestion with strategy logic, model research, execution, dashboard rendering, or global storage policy.

## In Scope

- Define component-local data ingestion workflows.
- Connect to approved market data, macro data, calendar, options, and related data sources once providers are chosen.
- Normalize provider responses into documented data shapes for market board data, instrument data, and option data.
- Validate data completeness, schema expectations, timestamps, market calendars, and known provider quirks.
- Produce data artifacts for downstream repositories.
- Produce run manifests and ready signals using `trading-main` contracts once concrete schemas are accepted.
- Coordinate with `trading-storage` for durable output placement and retention rules.
- Expose component-local tests for data parsing, validation, and fixture-based provider behavior.
- Track data-provider limitations, quotas, and quality caveats that affect this repository.
- Build provider/source connector layer boundaries before domain pipelines depend on live APIs.

## Out of Scope

- Defining global artifact, manifest, ready-signal, or request contracts.
- Owning shared storage layout, backup, archive, restore, or retention policy.
- Strategy implementation or backtesting.
- Model training, market-state discovery, or strategy-result analysis.
- Live or paper trade execution.
- Dashboard frontend or backend implementation.
- Promotion, scheduling, retry policy, or lifecycle orchestration owned by `trading-manager`.
- Storing generated data, raw provider dumps, logs, notebooks, credentials, or secrets in Git.
- General-purpose data platform work unrelated to the trading system.

## Owner Intent

`trading-data` should become a disciplined data-producing component: narrow enough to be auditable, but strong enough that downstream repositories can trust its artifacts and manifests.

The repository should prefer explicit provider boundaries, deterministic normalization, fixture-backed tests, and documented quality checks over ad hoc scripts.

## Boundary Rules

- `trading-data` owns data acquisition and data-output production; it does not own downstream interpretation.
- Cross-repository artifact, manifest, ready-signal, request, field, status, and type definitions belong in `trading-main`.
- Durable storage layout and retention belong in `trading-storage`.
- Scheduling, retries, and lifecycle routing belong in `trading-manager`.
- Generated data and provider responses are runtime artifacts, not source files.
- Secrets, API keys, provider tokens, broker credentials, and exchange keys must stay outside the repository and be referenced only by approved secret aliases.
- Shared helpers, templates, and registrable fields discovered here must be recorded through `trading-main` before other repositories depend on them.
- Data features emitted here must be market/data-source based. Strategy returns or strategy performance must not feed upstream data production.

## Out-of-Scope Signals

A request should be rejected or re-scoped if it asks `trading-data` to:

- implement strategy, model, execution, or dashboard logic;
- commit generated datasets, raw dumps, logs, or notebooks;
- store secrets or credentials;
- define global contracts without routing them through `trading-main`;
- invent shared field/status/type names without registry review;
- bypass `trading-storage` for durable layout policy;
- use strategy performance to define upstream market data features;
- become a one-off script dump without tests, contracts, or acceptance evidence.
