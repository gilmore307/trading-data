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

## D017 - Data tasks are manager-driven historical acquisitions

Date: 2026-04-26

### Context

The user clarified that current data acquisition work is historical data only. Realtime data belongs to trade execution later. Data acquisition should be initiated by `trading-manager` through a task key file containing all information needed for `trading-data` to complete the task.

### Decision

`trading-data` will treat manager task key files as its workflow input. A task key names the historical acquisition script/bundle, parameters, source references, credential aliases or no-key confirmations, and the output destination. During development, `trading-data` writes cleaned data and a task completion receipt under `storage/`; durable storage SQL destinations and storage-resident receipts wait for accepted `trading-storage` contracts.

### Rationale

This keeps orchestration in `trading-manager`, historical data acquisition in `trading-data`, durable storage in `trading-storage`, and realtime execution behavior out of the data repository.

### Consequences

- Realtime feeds are out of scope for `trading-data`.
- Script boundaries are organized by data type / usage bundle.
- The exact task key schema, development output layout, SQL table contract, and durable completion receipt schema remain pending cross-repository contract work.
- Default tests must use fixtures/mocks and must not require live provider calls.

## D018 - Macro release acquisition was initially split by release event

Date: 2026-04-26

### Context

The initial acquisition bundle plan included a broad macro release bundle across FRED, Census, BEA, BLS, Treasury, and official agency pages. The user clarified that macro data from different institutions has different publication times and is usually not consumed simultaneously.

### Decision

This decision was superseded later on 2026-04-26. The current accepted bundle is `macro_data`, with source/release/series selection moved into task params.

### Rationale

Release-time alignment matters for historical market context and avoids accidental lookahead or stale-data mixing. Separate bundles also make manager task keys more precise and easier to replay.

### Consequences

- Superseded: do not create separate registry bundles for each macro release by default.
- Connector work must still preserve release timestamp/window, covered period, revision/vintage evidence, and source URL in task params and receipts.
- Macro source/release inventory remains useful as parameter vocabulary, not as bundle inventory.

## D019 - Development data outputs use local storage instead of SQL

Date: 2026-04-26

### Context

The previous workflow described writing cleaned historical data rows to storage SQL targets once contracts are accepted. The user clarified that during development, data should not be written into SQL because that would dirty the database and make cleanup harder.

### Decision

During development, `trading-data` task outputs and development completion receipts should be written as ignored local files under `storage/`. SQL writes are deferred until a durable `trading-storage` contract is accepted or an explicitly guarded integration path is approved.

### Rationale

Local files are easier to inspect, delete, and regenerate while schemas, task keys, and provider connectors are still changing. This avoids polluting durable databases during early development.

### Consequences

- Registered config `TRADING_DATA_DEVELOPMENT_STORAGE_ROOT` points to `storage`.
- `.gitignore` keeps generated contents under `storage/` out of Git.
- Implementation should group outputs by task/run under the development storage root.
- Future SQL table/partition contracts remain `trading-storage` work.

## D020 - API-specific bundles require template design before code

Date: 2026-04-26

### Context

The user approved designing templates around concrete API requirements before implementing source bundles. Each bundle will eventually have fetch, clean, save, and receipt steps.

### Decision

Before connector code lands, each bundle should be designed using `trading-main/templates/data_tasks/`: task key, bundle README, fetch spec, clean spec, save spec, completion receipt, and fixture policy.

### Rationale

Provider/API requirements differ significantly. A template design gate keeps credentials, rate limits, timestamp semantics, raw/cleaned outputs, development storage, and receipt evidence explicit before implementation.

### Consequences

- `docs/09_api_templates.md` owns the component guide for applying the templates.
- Source bundle folders should not be created as ad hoc scripts without filled API requirements.
- Stable fields or status values discovered while filling templates must route through `trading-main` registry review.

## D021 - Source bundles default to one pipeline file

Date: 2026-04-26

### Context

The previous source folder plan used separate `fetch.py`, `clean.py`, `save.py`, and `receipt.py` modules for every bundle. The user approved simplifying this into one file per bundle by default while keeping the four processing stages as internal functions.

### Decision

Each bundle should start with one `pipeline.py` file containing `run(...)`, `fetch(...)`, `clean(...)`, `save(...)`, and `write_receipt(...)`. Bundle-specific API details belong in the bundle README. Split step functions into separate modules only when complexity justifies it.

### Rationale

One pipeline file keeps early development simple and makes manager invocation straightforward. Internal step functions preserve replay, test, and failure-evidence boundaries.

### Consequences

- Future source folder shape is `src/trading_data/data_sources/<bundle>/README.md` plus `pipeline.py`.
- `trading-main/templates/data_tasks/pipeline.py` is the default implementation template.
- The fetch/clean/save/receipt spec templates remain design documents, not required separate Python files.

## D022 - Runtime JSON templates stay minimal

Date: 2026-04-26

### Context

The user pointed out that fields such as provider documentation URL do not serve the task-key or receipt runtime use case and should not be pushed into JSON templates.

### Decision

Keep task key and completion receipt JSON minimal. Runtime JSON should include only fields consumed by manager, runner, bundle execution, output location, or receipt readers. Provider documentation URLs and explanatory metadata belong in registry/provider docs or bundle README/specs.

### Rationale

This prevents over-designed templates and keeps manager-generated task keys easy to produce and validate.

### Consequences

- Bundle-specific details remain in README/spec templates.
- Task key bundle-specific inputs should usually go under `params`.
- New runtime JSON fields require a clear consumer.

## D023 - Stable task keys may have many runs

Date: 2026-04-26

### Context

The user clarified that one task may have multiple runs, for example when it is periodic or scheduled. The task key should remain fixed while run-specific data changes each invocation.

### Decision

Keep task keys stable. Record each invocation as an entry in task-level completion receipt `runs[]`, with run id, status, timestamps, output directory, outputs, row counts, and error.

### Rationale

This keeps the task definition stable and lets manager compare or inspect runs without creating a new task key for every scheduled invocation.

### Consequences

- `task_key.json` uses `output_root`.
- Run outputs live under `storage/<task-id>/runs/<run-id>/`.
- `completion_receipt.json` lives at task level and contains `runs[]`.
- `pipeline.py` receives `run_id` separately from the task key.

## D024 - Macro data uses one parameterized bundle

Date: 2026-04-26

### Context

After reviewing separate macro release and Treasury source bundle planning, the user judged the bundle inventory too fragmented. The desired shape is one macro acquisition bundle with task parameters selecting the concrete data.

### Decision

Use one accepted macro bundle key: `macro_data`.

The bundle covers FRED, Census, BEA, BLS, U.S. Treasury Fiscal Data, and official macro source pages. Task params must specify the provider/source, dataset or release key, series identifiers when applicable, cadence, covered period/time range, publication or revision behavior, source URL, credential/no-key rule, and output target.

### Rationale

A single macro bundle keeps manager routing and bundle inventory clear. Macro data still needs precise source and release semantics, but those details belong in input params and bundle-specific validation rather than in many registry bundle rows.

### Consequences

- Do not register separate macro bundles merely because data comes from a different macro agency.
- `macro_release_<release_key>` and `treasury_fiscal_data` are superseded as registry bundle keys.
- Macro task params must be stricter because the bundle name no longer carries the release/source boundary.
- A macro source/release inventory is still needed, but it should feed parameter validation and docs rather than bundle proliferation.

## D025 - FRED only fetches FRED-unique macro data by default

Date: 2026-04-26

### Context

The user clarified that the same economic measure should use one unified, consistent data source. FRED aggregates many BLS, BEA, Census, Treasury, and other official series, but using FRED and official agencies interchangeably would create duplicate acquisition paths and possible inconsistencies.

### Decision

Use official agency sources as canonical for their own measures. Use FRED only for FRED/St. Louis Fed/ALFRED-unique data or explicitly approved FRED-native research series/groups.

### Rationale

Consistent source ownership avoids duplicate rows, conflicting revisions, mismatched metadata, and uncertainty about which version of a measure downstream research used.

### Consequences

- `macro_data` params may use `source = "fred"` only for FRED-unique/approved FRED-native series.
- BLS, BEA, Census, Treasury, and other official-agency measures should use their official source params by default.
- Any exception that uses FRED for an official-agency measure needs explicit review and documentation of why FRED is the chosen canonical path.

## D026 - Final output templates are generated from registry ids

Date: 2026-04-27

### Context

The final data-kind CSV/JSON preview files define the output shapes consumed by downstream models and research code. The user clarified that generated outputs should use stable registry ids as the source of field names instead of hand-typed column/key text, and that static preview files should be materialized templates generated by script.

### Decision

Treat `storage/templates/data_kinds/**/*.preview.csv` and `*.preview.json` as generated materialized output templates. Generate them from `src/trading_data/template_generators/data_kind_previews.py`, where template specs refer to stable `trading-main` registry ids and resolve current payload field names from `registry/current.csv`.

### Rationale

Registry ids are durable while display keys and field payload text can be renamed. Generating output templates from ids keeps committed previews human-readable while avoiding hand-maintained column/key text as the source of truth.

### Consequences

- Do not hand-edit data-kind preview CSV/JSON files directly.
- Edit the generator/spec and registry entries, then regenerate previews.
- CI/local validation should run the generator in `--check` mode to catch stale previews.
- Static README prose remains hand-written, but fields changed under `artifact_sync_policy=sync_artifact` must be synchronized with the generated previews and relevant docs.

## D027 - Nested final artifacts use local JSON in development and SQL JSONB durably

Date: 2026-04-27

### Context

`option_chain_snapshot` is a nested final artifact: one snapshot contains a complete option-chain structure with many contracts and nested quote, IV, Greeks, derived, and underlying context. During development, `trading-data` still writes local ignored files under `storage/`, while production durability will move to SQL contracts owned by `trading-storage`.

### Decision

For development-stage bundle implementation, save `option_chain_snapshot` as a final JSON file. For the final durable SQL contract, store the complete normalized nested artifact in a PostgreSQL `jsonb` column inside the SQL row, not as an external JSON file path.

### Rationale

A JSON file keeps development simple and reviewable while the durable storage contract is still being shaped. SQL JSONB later preserves the same nested final artifact shape inside transactional, queryable, backupable storage without prematurely splitting contract rows into many child tables.

### Consequences

- Development output remains a local ignored JSON file.
- Production storage should treat the JSONB row body as the canonical durable final artifact for `option_chain_snapshot`.
- Contract-level projection tables or materialized views may be added later for query acceleration, but they should be derived from the canonical JSONB artifact unless a later storage decision supersedes this.
- The bundle does not need file-level partial resume for the final artifact; a failed durable SQL transaction should leave no partial final snapshot.

## D028 - Option primary tracking aggregates active ThetaData OHLC rows

Date: 2026-04-27

### Context

ThetaData `/v3/option/history/ohlc` returns specified-contract 1-second OHLC rows and may include zero-volume placeholder rows. The `thetadata_option_primary_tracking` bundle must track a contract supplied by the task key without becoming a contract-selection model.

### Decision

Require task params to provide `underlying`, `expiration`, `right`, `strike`, `start_date`, `end_date`, and `timeframe`. Fetch ThetaData option OHLC rows, keep provider rows transient, skip rows whose `volume` and `count` are both zero, aggregate active rows to the requested `America/New_York` timeframe, and save final `option_bar.csv` only under `saved/`.

### Rationale

The specified contract is an input, so selection remains outside the data bundle. Filtering zero placeholders prevents no-trade seconds from becoming false bars. Aggregating to a task-key `timeframe` keeps option bars aligned with equity/crypto bar conventions and downstream research inputs.

### Consequences

- `thetadata_option_primary_tracking` does not select contracts.
- Cleaned JSONL may exist only as run-local development evidence.
- Final saved flat output is `option_bar.csv`.
- VWAP is calculated from active 1Sec close × volume because the source OHLC `vwap` field is not treated as a per-second trade VWAP.

## D029 - Option event timeline carries task/model current standards

Date: 2026-04-27

### Context

`option_activity_event` is a news-like final output and should contain only triggered event rows. The triggering standard is model/run-specific and must not become a hidden global constant inside `trading-data`.

### Decision

Require `thetadata_option_event_timeline` task params to include a `current_standard` object with the indicator standards used for that run. The bundle fetches transient ThetaData trade/quote rows, evaluates supplied standards over `America/New_York` evidence windows, emits final `option_activity_event.csv` rows only when an indicator triggers, and writes one compact `<event_id>.json` detail artifact per event containing objective statistics, current standards, and standard context.

### Rationale

The data bundle can preserve event-time evidence without pretending to own the model standard. Keeping `summary` abnormal-type-only and pushing metrics/current-standard values into the detail artifact preserves the simplified timeline shape while keeping audit context available.

### Consequences

- `current_standard` values are task/model inputs, not global `trading-data` constants.
- `summary` contains only triggered abnormal indicator type names.
- Raw trade/quote rows and window process state remain transient.
- Event ids and standard ids use semantic prefixes with random suffixes only; they do not encode timestamp, contract, or trigger semantics.
- Model-standard identity/versioning remains future `trading-model` work.

## D042 - Unified event database layer

Financial reports, SEC corporate filings, news, option activity, macro releases, and market anomalies should be studied through a shared event database layer rather than as isolated source-specific tables.

Raw acquisition remains source-specific. Source bundles such as `sec_company_financials`, `alpaca_news`, and `thetadata_option_event_timeline` own official/provider fetches and source-local normalization. Event builders project those outputs into source-neutral `trading_event` rows.

Long-form agent/model interpretation belongs in artifact files, with `event_analysis_report` indexing the Markdown report and structured JSON sidecar. `trading_event` rows store facts, timing, source references, short summaries, and report URLs only. `event_factor` rows store numeric model-facing scores such as direction, magnitude, surprise, novelty, relevance, credibility, price-in, and observable reaction.

`event_time_et` is the source publication/detection timestamp. `effective_time_et` is the earliest trading timestamp when the event can safely be observed by a strategy. This distinction is mandatory to prevent look-ahead leakage, especially for after-hours filings and news.
