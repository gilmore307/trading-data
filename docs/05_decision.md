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

Superseded in part by D051 for accepted SQL-only bundle contracts.

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

## D024 - Macro data uses one parameterized bundle [superseded by D050]

Date: 2026-04-26

### Context

After reviewing separate macro release and Treasury source bundle planning, the user judged the bundle inventory too fragmented. The desired shape is one macro acquisition bundle with task parameters selecting the concrete data.

### Decision

Use one accepted macro bundle key: `macro_data`.

Superseded on 2026-04-28 by D050: `macro_data` is removed as an executable bundle and Trading Economics visible calendar rows are the accepted macro model-input source.

The bundle covers FRED, Census, BEA, BLS, U.S. Treasury Fiscal Data, and official macro source pages. Task params must specify the provider/source, dataset or release key, series identifiers when applicable, cadence, covered period/time range, publication or revision behavior, source URL, credential/no-key rule, and output target.

### Rationale

A single macro bundle keeps manager routing and bundle inventory clear. Macro data still needs precise source and release semantics, but those details belong in input params and bundle-specific validation rather than in many registry bundle rows.

### Consequences

- Do not register separate macro bundles merely because data comes from a different macro agency.
- `macro_release_<release_key>` and `treasury_fiscal_data` are superseded as registry bundle keys.
- Macro task params must be stricter because the bundle name no longer carries the release/source boundary.
- A macro source/release inventory is still needed, but it should feed parameter validation and docs rather than bundle proliferation.

## D025 - FRED only fetches FRED-unique macro data by default [superseded for active routing by D050]

Date: 2026-04-26

### Context

The user clarified that the same economic measure should use one unified, consistent data source. FRED aggregates many BLS, BEA, Census, Treasury, and other official series, but using FRED and official agencies interchangeably would create duplicate acquisition paths and possible inconsistencies.

### Decision

Use official agency sources as canonical for their own measures. Use FRED only for FRED/St. Louis Fed/ALFRED-unique data or explicitly approved FRED-native research series/groups.

Superseded for active `trading-data` manager routing on 2026-04-28 by D050: official macro APIs and FRED/ALFRED aliases may remain stored, but macro model inputs now use Trading Economics visible calendar rows.

### Rationale

Consistent source ownership avoids duplicate rows, conflicting revisions, mismatched metadata, and uncertainty about which version of a measure downstream research used.

### Consequences

- `macro_data` params may use `source = "fred"` only for FRED-unique/approved FRED-native series.
- BLS, BEA, Census, Treasury, and other official-agency measures should use their official source params by default.
- Any exception that uses FRED for an official-agency measure needs explicit review and documentation of why FRED is the chosen canonical path.

## D026 - Final output templates are generated from registry ids

Date: 2026-04-27
Status: Superseded by D059 for current development

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

`event_time` is the source publication/detection timestamp. `effective_time` is the earliest trading timestamp when the event can safely be observed by a strategy. This distinction is mandatory to prevent look-ahead leakage, especially for after-hours filings and news.

## D043 - News covered by official SEC events is not an independent alpha event

News articles that merely report or summarize an official SEC filing should not create separate independent event alpha when the SEC filing is already represented as the canonical event. Raw news remains preserved in the source-specific acquisition layer, but the unified event layer must either suppress the duplicate news event or mark it as covered by the canonical official event.

Use `canonical_event_id`, `dedup_status`, `source_priority`, and `coverage_reason` to record this boundary. Official SEC/exchange/company/regulatory disclosures outrank derivative news coverage. Covered news can still contribute to propagation, attention, or report context, but it should not create an extra `event_factor` row unless it contains genuinely new information not already present in the official source and that information is observable at its own `effective_time`.

## D044 - Event impact scope is explicit

Unified event rows must identify whether the event primarily affects the broad market, a sector, an industry, a theme, one security, multiple securities, macro conditions, or an unresolved target. Use `impact_scope`, `impacted_universe`, and `primary_impact_target` so broad events are not accidentally scored as single-stock events and single-name events are not wrongly propagated to an entire sector.

`security_id`/`symbol` remains the primary tradable identifier when one exists, but it is not enough to describe impact. For example, a company 10-K is normally `impact_scope=security`, while a CPI release may be `impact_scope=market` with `impacted_universe=US_MARKET;rates;USD`.

## D045 - Macro releases are event-layer objects [superseded for source path by D050]

Macroeconomic publications such as CPI, payrolls, PCE, GDP, and rate decisions are not only indicator values. They are market-impact events because the publication moment can move broad markets, rates, FX, sectors, and securities immediately.

Keep source evidence and final saved outputs separate:

- `macro_release` is transient cleaned source evidence for observed values and release-time validity. It is not a final saved/model-facing alpha table.
- `macro_release_event` is the final saved event-layer object with `event_type=macro_release_event`, `source_type=official_macro_release`, impact scope/universe, source reference, actual value attributes, and report/factor linkage.

The `macro_data` bundle should save `macro_release_event.csv` as the final output and keep `macro_release.jsonl` only under `cleaned/` as run-local evidence. Event studies and reaction labels should use `macro_release_event`. Market-state models should use pure market/index/ETF data for state classification rather than macro reason labels. Official macro APIs usually provide actual values but not consensus expectations, so surprise fields remain pending until an approved consensus source exists.

Superseded for active source path on 2026-04-28 by D050: `macro_data` is removed, and macro model inputs now use Trading Economics visible calendar rows with Actual, Previous, Consensus, and Forecast when visible.

## D046 - GDELT is the primary broad news source

Alpaca news remains useful for stock-specific provider coverage, but GDELT is the primary broad news/event discovery source for political, economic, technology, geopolitical, sector, industry, theme, and market-impact event candidates.

`gdelt_news` saves `gdelt_article` source-evidence rows from GDELT BigQuery. These rows are not canonical event identity by themselves. Downstream event extraction/clustering must merge GDELT articles into `trading_event` / `event_factor`, respect official-source priority, and avoid duplicate alpha counting when SEC/company/regulatory disclosures already cover the same event.

## D047 - GDELT acquisition is U.S./U.S.-market focused by default

The system does not need all global GDELT news. `gdelt_news` should pre-filter in BigQuery for U.S. and U.S.-market relevance by default, using `focus=us_market`, U.S. location/market terms, and a curated U.S./U.S.-market source-domain allowlist. Broader global queries require an explicit `focus=none` task parameter and should be treated as exceptional research, not the production default.

## D048 - GDELT default topics are politics, economy, war, and technology

`gdelt_news` should not be an open-ended news firehose. Its default query scope is U.S./U.S.-market news in four market-impact categories: politics, economy, war/geopolitics, and technology. If a task omits `query_terms`, the bundle expands those categories into a bounded default term set. Other categories require explicit task parameters and should be reviewed before becoming production defaults.

## D049 - Seven model input bundles organize data products by model layer

Date: 2026-04-28

### Context

The accepted `trading-model` architecture now has seven layers. Source acquisition is sufficiently complete for v1, but model-specific data needs require a clear organization layer before final cleaning, derived features, and table shapes are hardened.

### Decision

`trading-data` will organize model-facing inputs into seven registered input bundles:

1. `market_regime_model_inputs`
2. `security_selection_model_inputs`
3. `strategy_selection_model_inputs`
4. `trade_quality_model_inputs`
5. `option_expression_model_inputs`
6. `event_overlay_model_inputs`
7. `portfolio_risk_model_inputs`

These are organization bundles, not necessarily new raw-source acquisition bundles. They map existing source outputs and derived products to model-layer needs.

### Rationale

Model needs should drive data organization. This prevents raw-source tables from dictating model schemas and keeps layer boundaries clear.

### Consequences

- `docs/11_model_inputs.md` owns the current mapping from source outputs to model input bundles.
- `SecuritySelectionModel` requires `stock_etf_exposure` derived from ETF holdings and ETF/sector/style scores.
- `EventOverlayModel` requires `equity_abnormal_activity_event` in addition to GDELT, SEC, Trading Economics, macro, and option activity data.
- `PortfolioRiskModel` depends partly on portfolio/account state that may be execution/account-owned rather than pure `trading-data`.

## D050 - Trading Economics replaces macro_data for macro model inputs

Date: 2026-04-28

### Context

`macro_data` previously acted as a parameterized official macro API bundle for BLS, BEA, Census, Treasury, and FRED/ALFRED-style rows. The project now prioritizes model-facing macro calendar/value rows with Actual, Previous, Consensus, and Forecast fields from Trading Economics visible pages.

### Decision

Remove `macro_data` as an executable `trading-data` acquisition bundle. Macro model inputs should use `trading_economics_calendar_web` visible-page rows.

Official macro API keys and secret aliases may remain stored and registered for optional future research, but they are not active manager task routes.

### Consequences

- Do not route manager-issued tasks to `macro_data`.
- Do not add new `macro_data` source interfaces or tests.
- Keep Trading Economics constraints: visible page only, no TE API, no Download/export endpoint, and no WAF/captcha/permission bypass.
- Deprecated registry/template rows may remain as historical references until a broader registry cleanup is explicitly accepted.

## D051 - Market regime model inputs are SQL-only

Date: 2026-04-28

### Context

The first MarketRegimeModel bundle now fetches ETF bars directly from the configured ETF universe over a manager-supplied time range. The user accepted SQL-only saved output for this bundle instead of CSV/debug artifacts.

### Decision

`01_bundle_market_regime` writes its canonical saved output to SQL table `trading_data_01_bundle_market_regime`. The table is a single long table across symbols and bar grains, keyed by `run_id + symbol + timeframe + timestamp`.

### Consequences

- Do not write `saved/01_bundle_market_regime.csv` or cleaned JSONL for the final model input output.
- Keep `timeframe` as an explicit column; downstream features must group/filter by `symbol + timeframe`.
- D019 remains the default for legacy bundles, but is superseded for accepted SQL-only bundle contracts.

## D052 - SQL-only model inputs target PostgreSQL, not local SQLite

Date: 2026-04-28

### Context

After accepting SQL-only output for `01_bundle_market_regime`, the first implementation used SQLite as a local minimal SQL target. The user clarified that the project should prepare directly for a formal large SQL backend instead of encoding SQLite as the output contract.

### Decision

Accepted SQL-only model input bundles target a configured PostgreSQL storage target. Tests may inject fake SQL writers, but production bundle semantics must not hard-code SQLite files or local database paths.

`01_bundle_market_regime` uses `storage_target.driver = "postgresql"`, target schema `trading_data`, and table `trading_data_01_bundle_market_regime`.

### Consequences

- Use `format = "sql_table"` for bundle output contracts, not `sqlite`.
- Runtime credentials come from a storage secret alias such as `trading_storage_postgres`.
- Receipt details should record receipt-safe target/table metadata, not database credentials or local SQLite paths.
- Local SQLite is not the canonical development or production output for accepted SQL-only model inputs.

## D053 - Model input bundle manifests are SQL tables

Date: 2026-04-28
Status: Superseded by D054-D061 for active numbered bundles

### Context

After `01_bundle_market_regime` became SQL-only, the remaining numbered model input bundles still emitted saved CSV manifest files. That left the seven-bundle model input layer split between formal SQL and temporary local artifacts.

### Decision

Historical decision: model input bundle manifests for layers 2-7 were SQL-only and wrote to `model_inputs.model_input_artifact_reference`; Layer 1 remained a specialized bar table. This manifest approach has been superseded by specific bundle output tables under the `trading_data` schema.

The old shared manifest table stored point-in-time artifact references keyed by `run_id + bundle + input_role + data_kind + artifact_reference`.

### Consequences

- Do not write `saved/<bundle>.csv` for layers 2-7.
- Use the shared PostgreSQL storage target configured by each bundle's `storage_target`.
- Tests inject fake SQL writers; production uses the PostgreSQL writer.
- Artifact-producing internal steps, such as `stock_etf_exposure` derivation inside Layer 2, remain separate implementation details until their own final SQL contracts are accepted.

## D054 - Security selection bundle writes filtered ETF holdings

Date: 2026-04-28

### Context

Layer 2 was incorrectly treated as a generic model-input artifact manifest, and a proposed bar-shaped output duplicated Layer 1. The user clarified that bars belong to `01_bundle_market_regime`; `02_bundle_security_selection` should produce ETF holdings for security selection.

### Decision

`02_bundle_security_selection` accepts `params.start` and `params.end`, uses `storage/shared/market_etf_universe.csv` for ETF universe/issuer/exposure labels, collects issuer holdings snapshots, filters holdings to US-listed equity constituents, and writes SQL table `trading_data.trading_data_02_bundle_security_selection`.

The output excludes non-model fields such as `cusip`, `sedol`, raw `asset_class`, and `source_url`. Task write/audit timestamps belong in completion receipts, not this business table. `available_time` remains because it defines when the holding row is visible to model logic and prevents lookahead.

### Consequences

- Layer 2 no longer writes the shared `model_input_artifact_reference` manifest as its final output.
- Layer 2 does not write bars; Layer 1 owns bars.
- Filter out cash, money-market, fixed income, futures, swaps, options, funds, non-US local listings, and other non-equity assets unless explicitly reviewed later.
- Primary key: `run_id + etf_symbol + as_of_date + holding_symbol`.

## D055 - Strategy selection bundle writes bar plus liquidity inputs

Date: 2026-04-28

### Context

Layer 3 was still represented as a generic artifact-reference manifest. The user clarified that `03_bundle_strategy_selection` receives manager-selected symbols plus a start/end window, defaults to 1-minute data, and should output bar plus liquidity inputs. Liquidity rules and feature windows already belong elsewhere and should not be added to this bundle config. Derived features such as returns, volatility, trend strength, and gap percentage should not be fabricated by this raw input bundle.

### Decision

`03_bundle_strategy_selection` accepts `params.start`, `params.end`, and `params.symbols`, fetches Alpaca bars plus transient trades/quotes, aggregates liquidity by interval, and writes SQL table `trading_data.trading_data_03_bundle_strategy_selection`.

The output includes OHLCV/VWAP/trade count, dollar volume, quote count, average bid/ask/depth/spread, spread bps, and last bid/ask. It does not include created/write timestamps or downstream feature/model columns.

### Consequences

- Layer 3 no longer writes the shared `model_input_artifact_reference` manifest as its final output.
- Raw trades/quotes remain transient and are not persisted by default.
- Feature engineering for returns/volatility/trend/gaps remains downstream of this data bundle.
- Primary key: `run_id + symbol + timeframe + timestamp`.

## D056 - Trade quality has no trading-data bundle; option expression writes option snapshot

Date: 2026-04-28

### Context

The user clarified that `TradeQualityModel` does not require a `trading-data` bundle, SQL view, or manifest contract because it does not fetch new data. It consumes upstream SQL outputs and model/strategy candidates. The next model-input acquisition need is `OptionExpressionModel`, which needs a point-in-time option snapshot.

### Decision

Remove active `04_trade_quality_model_inputs` from `trading-data` runnable bundles. `TradeQualityModel` inputs are constructed by `trading-model` from existing upstream SQL outputs and candidate signal artifacts.

`05_bundle_option_expression` is a real data bundle. It accepts `underlying` and `snapshot_time`, calls the ThetaData option selection snapshot source interface, and writes SQL table `trading_data.trading_data_05_bundle_option_expression` with one row per requested snapshot and a nested `contracts` JSONB payload.

### Consequences

- Do not keep a Layer 4 runnable data bundle or SQL manifest/view just for orchestration symmetry.
- Layer 5 owns option-chain snapshot acquisition for OptionExpressionModel inputs.
- Raw ThetaData responses remain transient; final durable payload is the normalized SQL row.
- Primary key for Layer 5: `run_id + underlying + snapshot_time`.

### D057 — Keep accepted model-input bundle defaults in code, not bundle-local config

Accepted: 2026-04-28

Decision: Remove bundle-local `config.json` files from the accepted 01, 02, 03, and 05 model-input bundles. Stable table contracts, storage defaults, source aliases, and request defaults live in reviewed pipeline code. Manager-supplied values remain in task keys, and reviewed shared universes remain shared artifacts such as `/root/projects/trading-main/storage/shared/market_etf_universe.csv`.

Rationale: The removed config files duplicated code-level contracts and made table schemas, storage targets, and defaults look operator-tunable when they are actually semantic contracts. Keeping them in code reduces drift and makes contract changes reviewable.

Consequences:

- `params.config_path` is no longer part of accepted 01/02/03/05 bundle contracts.
- Tests inject fake SQL writers instead of overriding storage config.
- One-off universe overrides remain possible through explicit task params where useful for tests/review.
- Future config files should be added only when a value is intentionally operator-managed outside code review.

### D058 — Reorder execution and event overlay model-input bundles

Accepted: 2026-04-28

Decision: Layer 06 is now `PositionExecutionModel` / `06_bundle_position_execution`, and Layer 07 is now `EventOverlayModel` / `07_bundle_event_overlay`. The old manifest-style `06_event_overlay_model_inputs` and `07_portfolio_risk_model_inputs` bundle shells are removed.

Rationale: OptionExpressionModel chooses the theoretically best-return and risk-controllable contracts. The next layer should study how to execute those selected contracts, requiring option contract time-series data from entry through exit plus one hour. Event overlay is a later global context layer and should use one event overview table rather than manifest references.

Consequences:

- Layer 06 writes `trading_data.trading_data_06_bundle_position_execution`.
- Layer 07 writes `trading_data.trading_data_07_bundle_event_overlay`.
- `07_bundle_event_overlay/equity_abnormal_activity` remains a nested detector feeding event overlay prior-signal rows.
- Old `model_input_artifact_reference` manifest behavior should not be expanded for accepted numbered bundles.

## D059 - Retire data-kind preview templates

Accepted: 2026-04-28

The old `storage/templates/data_kinds/` preview catalog and `trading_data.template_generators.data_kind_previews` generator are retired. Dedicated SQL storage definitions and bundle/source README contracts now own accepted output shapes.

Consequences:

- Do not add new `*.preview.csv` or preview JSON files under `storage/templates/data_kinds/`.
- Do not run or depend on the removed `trading-data-generate-data-kind-templates` command.
- Field registration should target final SQL tables and still-valid shared/task/receipt/registry artifacts, not historical preview files.
- Older D026 is superseded for current development; it remains historical context only.

## D060 - Numbered packages are data bundles, not complete model-input universes

Date: 2026-04-28
Status: Accepted

### Context

The active numbered packages under `src/trading_data/data_bundles/` were named `*_model_inputs`, which overstated their boundary. They do not construct every input a model consumes; they only fetch and prepare the data-source-backed portion needed by each model layer.

### Decision

Rename active numbered packages to `NN_bundle_<layer>`:

- `01_bundle_market_regime`
- `02_bundle_security_selection`
- `03_bundle_strategy_selection`
- `05_bundle_option_expression`
- `06_bundle_position_execution`
- `07_bundle_event_overlay`

CLI entrypoints now use `trading-data-NN-bundle-<layer>` names. SQL table names are handled separately; bundle outputs must not imply ownership of the complete model input universe.

### Consequences

- Do not add new active package/module names ending in `_model_inputs` under `data_bundles`.
- Bundle docs should describe the data fetched/prepared from sources, not claim ownership of the complete model-input universe.

## D061 - Bundle SQL table names follow bundle names

Date: 2026-04-28
Status: Accepted

### Context

The numbered data bundles wrote SQL tables with model-layer business names such as `market_regime_etf_bar` and `event_overlay_event`. Chentong clarified that this will become ambiguous once downstream training-data tables exist: these SQL outputs are `trading-data` bundle outputs, not complete model/training-data universes.

### Decision

Accepted numbered bundle SQL outputs use bundle-derived table names under the `trading_data` schema:

- `trading_data.trading_data_01_bundle_market_regime`
- `trading_data.trading_data_02_bundle_security_selection`
- `trading_data.trading_data_03_bundle_strategy_selection`
- `trading_data.trading_data_05_bundle_option_expression`
- `trading_data.trading_data_06_bundle_position_execution`
- `trading_data.trading_data_07_bundle_event_overlay`

Use snake_case for SQL identifiers; hyphenated names are only for CLI/package presentation where supported.

### Consequences

- Bundle output table names identify the producing `trading-data` bundle.
- Downstream training/model tables can later use their own precise names without colliding with source-backed bundle outputs.

## D062 - Bundle SQL outputs use trading_data schema, not model_inputs

Date: 2026-04-28
Status: Accepted

### Context

After bundle table names were changed to follow the producing `trading-data` bundle, Chentong clarified that the SQL schema name `model_inputs` is still wrong. A bundle output is not the model's full input set; models also consume upstream model outputs, candidate artifacts, feature tables, portfolio/execution state, and later training-data tables.

### Decision

Accepted numbered bundle SQL outputs live under schema `trading_data`, not `model_inputs`:

- `trading_data.trading_data_01_bundle_market_regime`
- `trading_data.trading_data_02_bundle_security_selection`
- `trading_data.trading_data_03_bundle_strategy_selection`
- `trading_data.trading_data_05_bundle_option_expression`
- `trading_data.trading_data_06_bundle_position_execution`
- `trading_data.trading_data_07_bundle_event_overlay`

The default PostgreSQL storage target id is `trading_data_postgres` and its schema is `trading_data`.

### Consequences

- Do not use `model_inputs` for source-backed `trading-data` bundle outputs.
- Future model/training repositories can own their own model-input or training-data schemas without semantic collision.
