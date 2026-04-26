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
