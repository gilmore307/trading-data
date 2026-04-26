# Decision

## D001 - `trading-data` owns upstream data production

Date: 2026-04-25

### Context

The trading system needs a clear boundary for data acquisition and normalization so downstream repositories do not depend on provider-specific details.

### Decision

`trading-data` owns component-local data ingestion, normalization, validation, artifact production, manifests, and ready signals for data outputs.

### Rationale

Separating data production prevents strategy, model, execution, and dashboard repositories from each inventing provider integrations or incompatible data shapes.

### Consequences

- Downstream repositories consume data artifacts and manifests, not provider internals.
- Provider integration work belongs here unless it is clearly component-specific elsewhere.
- Global contracts and shared vocabularies still belong in `trading-main`.

## D002 - Generated data is not repository content

Date: 2026-04-25

### Context

Data outputs, raw provider responses, logs, and runs may become large, sensitive, or volatile.

### Decision

Generated data, raw dumps, run outputs, logs, notebooks, and provider credentials must not be committed to `trading-data`.

### Rationale

Git should contain source, docs, tests, fixtures when approved, and small reviewable assets. Runtime outputs belong in storage systems governed by `trading-storage`.

### Consequences

- `.gitignore` excludes local data, artifacts, outputs, runs, logs, secrets, and local environments.
- Durable storage policy must be defined with `trading-storage` before production outputs depend on it.
- Test fixtures require explicit policy before provider responses are stored.

## D003 - Storage layout is delegated to `trading-storage`

Date: 2026-04-25

### Context

`trading-data` will produce durable artifacts, but shared persistence policy is a separate system concern.

### Decision

`trading-data` may write artifacts, but durable layout, retention, archive, backup, restore, and rehydrate rules are owned by `trading-storage`.

### Rationale

Keeping storage policy separate prevents each producer from inventing incompatible path layouts and retention assumptions.

### Consequences

- Data artifact writing must follow accepted `trading-storage` contracts once available.
- Until storage contracts exist, implementation must treat artifact paths as open gaps.
- `trading-data` docs should not claim final storage paths prematurely.

## D004 - Shared names route through `trading-main`

Date: 2026-04-25

### Context

Data work will likely introduce reusable fields, type values, templates, helper methods, provider-independent terms, and config keys.

### Decision

Any name or helper/template surface intended for cross-repository use must be recorded through `trading-main` before other repositories depend on it.

### Rationale

The trading registry and platform guides are the shared naming authority. Component-local invention would create drift and hidden contracts.

### Consequences

- New shared fields require `trading-main` registry review and non-empty `applies_to`.
- New global helpers belong under `trading-main/helpers/` and must be documented there.
- New reusable templates belong under `trading-main/templates/`.
- Temporary local names must be reported during completion/review if they may need registration.

## D005 - Default tests should avoid live provider calls

Date: 2026-04-25

### Context

External providers may have quotas, costs, credentials, rate limits, downtime, or data drift.

### Decision

Default tests should use fixtures, mocks, or deterministic local examples. Live provider tests require explicit opt-in guardrails.

### Rationale

Reliable tests should not depend on secrets, network state, paid quotas, or changing provider responses.

### Consequences

- Provider adapters should be designed for fixture-backed tests.
- Live tests must be clearly marked and guarded when introduced.
- Provider quotas and rate limits must be documented before automated live calls are accepted.

## D006 - Use the shared trading environment anchor

Date: 2026-04-25

### Context

`trading-main` anchors the shared local trading development environment at `/root/projects/trading-main/.venv`.

### Decision

`trading-data` should use the shared trading environment unless an explicit exception is accepted.

### Rationale

One shared environment reduces cross-repository drift during early platform development.

### Consequences

- Do not create a component-local `.venv/` as normal project structure.
- `.venv/` remains ignored if it appears locally.
- Dependency policy remains an open gap until the shared environment contract is defined.

## D007 - Optional component docs may document local planning surfaces

Date: 2026-04-25

### Context

The required docs spine covers scope, context, workflow, acceptance, tasks, decisions, and memory. `trading-data` also needs component-specific guides for data domains and data-source boundaries.

### Decision

Allow optional docs after `06_memory.md` when they own a clear component-specific planning surface and do not duplicate the required spine.

### Rationale

Provider and data-domain planning is too important to bury inside broad files, but it should remain docs-only until implementation contracts are accepted.

### Consequences

- `docs/07_data_domains.md` owns the market board, instrument, and option data-domain planning surface.
- `docs/08_data_sources.md` owns provider/source connector, API, token, and secret-alias planning boundaries.
- Optional docs must be listed in `docs/README.md`.

## D008 - Data work is organized into three purpose-driven domains

Date: 2026-04-25

### Context

The data repository will collect different data depending on downstream research purpose. The user identified three categories: market board data, instrument data, and option data. These correspond to later model lanes.

### Decision

Use three local planning domains: market board data / 盘面数据, instrument data / 标的数据, and option data / 期权数据.

### Rationale

Organizing by research purpose keeps provider composition and cleaning requirements explicit without mixing model training or strategy interpretation into data production.

### Consequences

- `trading-data` owns acquisition, cleaning, validation, and output production for these domains.
- `trading-model` owns later model training, labels, inference, and model evaluation.
- Exact domain keys are not cross-repository contract values until registered through `trading-main` if needed.

## D009 - Source connectors come before domain pipelines

Date: 2026-04-25

### Context

Each data domain is a composition of data from one or more providers. Implementation should first establish source connector boundaries, authentication, quotas, and provider capabilities before domain pipelines depend on live APIs.

### Decision

Treat data-source connection as the first implementation layer. Provider tokens, API keys, and credentials must live outside Git under `/root/secrets/` and be referenced by secret aliases. Shared/durable provider aliases should be registered as `config` rows in `trading-main` when providers are selected.

### Rationale

Provider connections are a boundary risk: secrets, quotas, timestamp semantics, and data-quality caveats must be explicit before cleaned outputs can be trusted.

### Consequences

- `docs/08_data_sources.md` owns provider/source connector planning.
- Default tests must not require live provider credentials.
- Provider choices and secret aliases remain open gaps until selected and reviewed.

## D010 - OKX is the first registered crypto provider config surface

Date: 2026-04-26

### Context

The user provided OKX API credentials and the OpenClaw server public IPv4 for OKX allowlisting. OKX is intended for crypto data acquisition and later trading access.

### Decision

Use OKX as the first registered crypto provider config surface. Store secret values only under `/root/secrets/okx/`; use `trading-main` registry config rows for secret aliases and non-secret metadata.

### Rationale

Provider access needs to be explicit before source connectors depend on it, but credentials must not enter Git. Registry config aliases give implementation a stable reference without exposing secret material.

### Consequences

- Registered aliases are `okx/api-key`, `okx/secret-key`, and `okx/passphrase`.
- Registered non-secret metadata includes allowed IPv4 `66.206.20.138` and API key remark `OpenClaw`.
- Default tests must still avoid live OKX calls unless explicitly guarded.
- Trading behavior remains outside `trading-data`; execution usage belongs to `trading-execution`.
