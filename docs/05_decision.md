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

Use OKX as the first registered crypto provider config surface. Store secret values only in `/root/secrets/okx.json`; use `trading-main` registry config rows for the source-level alias and non-secret metadata.

### Rationale

Provider access needs to be explicit before source connectors depend on it, but credentials must not enter Git. Registry config aliases give implementation a stable reference without exposing secret material.

### Consequences

- Registered source-level alias is `okx`, pointing to `/root/secrets/okx.json`; JSON keys are `api_key`, `secret_key`, `passphrase`, `allowed_ip_address`, and `api_key_remark_name`.
- OKX credential JSON includes `allowed_ip_address` for `66.206.20.138` and `api_key_remark_name` for `OpenClaw`; these are part of the source-level OKX credential bundle.
- Default tests must still avoid live OKX calls unless explicitly guarded.
- Trading behavior remains outside `trading-data`; execution usage belongs to `trading-execution`.

## D011 - Alpaca is the first registered stock and ETF data provider config surface

Date: 2026-04-26

### Context

The user provided Alpaca paper API credentials and endpoint for acquiring stock and ETF bars, quotes, trades, and news.

### Decision

Use Alpaca as the first registered stock/ETF data provider config surface. Store credentials and endpoint in `/root/secrets/alpaca.json`; use `trading-main` registry config row `ALPACA_SECRET_ALIAS` for the source-level alias.

### Rationale

Alpaca directly supports the initial non-crypto instrument data needs. Keeping its credentials and endpoint in one source JSON file follows the accepted source-secret pattern.

### Consequences

- Alpaca JSON fields are `api_key`, `secret_key`, and `endpoint`.
- Default tests must not require live Alpaca credentials or network calls.
- Any Alpaca connector implementation must document rate limits, timestamp semantics, and fixture/live-test policy before acceptance.

## D012 - ThetaData is registered for options data but connector layout is deferred

Date: 2026-04-26

### Context

The user identified ThetaData as the intended options-data provider for chain timeline, quote, trade, OHLC, Greeks, and related options datasets. ThetaData requires credentials to be stored in a `creds.txt` file beside `ThetaTerminalv3.jar`.

### Decision

Record ThetaData as the current registered options-data provider term, but defer connector implementation, JAR placement, and `creds.txt` placement until the source connector boundary is designed.

### Rationale

ThetaData's terminal-based credential requirement is different from source-level JSON providers such as OKX and Alpaca. It needs a deliberate local runtime layout before implementation.

### Consequences

- `trading-data` may plan options data around ThetaData.
- No ThetaData credentials or `creds.txt` are stored in this repository.
- Implementation remains blocked on connector/JAR/credential layout policy.

## D013 - Economic data providers are registered source-level API key surfaces

Date: 2026-04-26

### Context

The user provided API keys for FRED, Census, BEA, and BLS. These providers support macroeconomic, demographic, labor, and market-context data acquisition for data-domain planning.

### Decision

Use source-level secret aliases for FRED, Census, BEA, and BLS. Each source JSON uses the shared key `api_key`.

### Rationale

These providers match the standard source-level JSON secret pattern and should be available for later data-source connector implementation without exposing key values in Git.

### Consequences

- Registered config aliases are `FRED_SECRET_ALIAS`, `CENSUS_SECRET_ALIAS`, `BEA_SECRET_ALIAS`, and `BLS_SECRET_ALIAS`.
- Default tests must not require live credentials or network calls.
- Connector implementation must document rate limits, timestamp semantics, and fixture/live-test policy before acceptance.

## D014 - Provider documentation URLs live on provider term paths

Date: 2026-04-26

### Context

Data-source connector implementation will frequently need provider documentation. The registry has provider `term` rows and secret `config` rows, both with nullable `path` locators.

### Decision

Use provider `term` row `path` values for official documentation URLs. Keep secret `config` row `path` values pointed at local source-secret JSON files.

### Rationale

This lets connector work dereference documentation through the registry without confusing public docs with private credential files.

### Consequences

- Data-source docs list provider documentation paths.
- Credential lookup remains source-alias based.
- Default tests must still avoid live provider calls unless explicitly guarded.

## D015 - U.S. Treasury Fiscal Data is an open provider without a secret alias

Date: 2026-04-26

### Context

The user identified U.S. Treasury Fiscal Data as a likely no-key API source for federal finance datasets. The official documentation describes the API as open and not requiring a user account or token.

### Decision

Treat U.S. Treasury Fiscal Data as a registered provider term with a documentation path, but do not register a source-secret alias yet.

### Rationale

No-key/open APIs should not get unnecessary secret rows. The documentation URL is still useful as a registry-backed source connector reference.

### Consequences

- Provider term is `US_TREASURY_FISCAL_DATA`.
- No local `/root/secrets/treasury*.json` file is required.
- Connector implementation must still document dataset coverage, pagination, rate/usage behavior, timestamp semantics, and fixture/live-call policy.

## D016 - Web-discovered calendars and issuer ETF holdings require official sources

Date: 2026-04-26

### Context

The user identified FOMC calendar, official macro release calendars, and ETF holdings constituents/weights as required data-source surfaces. These sources are not necessarily credentialed APIs.

### Decision

Use the official Federal Reserve page for FOMC calendar data. Use web search to discover official macro release calendars, then accept only official government or issuing-agency pages as source of truth. Use ETF issuer websites or issuer-published holdings files for ETF constituent stocks and weights.

### Rationale

Calendar and holdings data are easy to corrupt through secondary aggregators. The source-of-truth rule must be explicit before connector or scraper work begins.

### Consequences

- Third-party macro calendars and ETF aggregators are secondary references only unless explicitly approved.
- Connectors must preserve source URL, retrieval timestamp, as-of/effective date, and file/page format.
- Default tests must use fixtures or mocks rather than live web search or issuer website calls.
