# Workflow

## Purpose

This file defines the intended data-production workflow for `trading-data`.

It describes how approved data requests become validated data artifacts, manifests, and ready signals without leaking provider-specific details into downstream repositories.

## Data Production Flow

`trading-data` is a historical-data acquisition component. Realtime feeds, live market streaming, and execution-time data handling belong to `trading-execution` unless a later reviewed contract explicitly re-scopes that boundary.

```text
manager task key file -> validate key -> classify data domain -> select acquisition script -> fetch historical data -> normalize -> validate -> write development files under data/storage -> write development task receipt under data/storage
```

Where:

- **manager task key file** is the manager-issued request/control file that contains enough information to complete the task without hidden chat context;
- **validate key** checks task identity, schema version, requested script/bundle, required parameters, destination expectations, idempotency key, and credential/source references;
- **classify data domain** maps the task to market board data, instrument data, option data, or a rejected/re-scoped request;
- **select acquisition script** invokes the data-type-specific source script named by the task key;
- **fetch historical data** calls external providers, official web sources, issuer websites, or approved local sources through documented source connectors;
- **normalize** converts provider-specific responses into accepted table-oriented data shapes;
- **validate** checks schema, timestamps, completeness, calendars, duplicates, and provider caveats;
- **write development files under `data/storage/`** stores cleaned outputs in the registered development local storage root instead of writing to SQL;
- **write development task receipt under `data/storage/`** records task status and evidence as a local file so runs remain inspectable and disposable during development.

The development storage root is registered as `TRADING_DATA_DEVELOPMENT_STORAGE_ROOT` with relative path `data/storage`. The exact task key file schema, future SQL table contract, and durable completion receipt schema remain cross-repository contract work with `trading-main` and `trading-storage`.

## Collaboration Flow

```mermaid
flowchart TD
  A[trading-manager Creates Data Task Key File] --> B[trading-data Validates Task Key]
  B --> C[Select Historical Acquisition Script]
  C --> D[Resolve Source Metadata and Secret Aliases]
  D --> E[Fetch Historical Source Data]
  E --> F[Normalize Rows]
  F --> G[Validate Dataset]
  G --> H[Write Cleaned Development Files under data/storage]
  H --> I[Write Development Task Receipt under data/storage]
  I --> J[trading-manager Lifecycle]
  I --> K[trading-model / trading-strategy / trading-dashboard via accepted contracts]
```

## Operating Principles

- Data acquisition is historical by default; realtime collection is out of scope for this repository.
- Data requests originate from `trading-manager`, not ad hoc local script calls.
- A task key file must be self-contained: no script may depend on missing chat context or implicit operator memory.
- Acquisition scripts are grouped by data type and repeated usage bundle, not merely by provider.
- Bundled scripts may fetch multiple related source records in one run, but outputs should remain separable by table/data type.
- Data requests should be idempotent where practical.
- Provider responses should be normalized before downstream exposure.
- Validation evidence belongs in completion receipts/manifests, not only logs.
- Downstream repositories should consume storage-backed outputs and receipts/manifests, not provider internals.
- Development outputs must stay under ignored `data/storage/`; SQL targets must not be used until `trading-storage` contracts are accepted or a guarded integration test explicitly opts in.
- Shared fields, statuses, and type names must come from `trading-main/registry/`.
- Live provider calls should be minimized in tests; prefer fixtures, recorded examples, or provider adapters with controlled mocks.


## Task Key File Requirements

The manager-issued task key file should eventually include at least:

- stable task identity;
- requested acquisition script or script bundle;
- target data domain;
- provider/source identifiers;
- symbols, underlyings, ETF identifiers, macro series, calendar scope, or source URLs as applicable;
- historical time range, snapshot timestamp, granularity, timezone, and market/session assumptions;
- source credential aliases or confirmation that no credential is required;
- provider-specific parameters;
- idempotency/replay key;
- stable development output root under `data/storage/<task-id>/`, plus future storage SQL destination/partition expectations when contracts exist;
- validation expectations;
- task-level development completion receipt destination under `data/storage/<task-id>/completion_receipt.json`, plus future durable receipt destination when contracts exist;
- priority, deadline, cancellation, and retry expectations when manager scheduling supports them.

The task key file is a contract surface, not an implementation shortcut. Its exact schema must be accepted through `trading-main` before code treats it as stable.



## API Template Design Gate

Before implementation creates a source bundle folder, the bundle should be designed from `trading-main/templates/data_tasks/`:

- task key shape;
- bundle README boundary;
- fetch requirements;
- clean/normalization requirements;
- save/output requirements;
- completion receipt shape;
- fixture/live-call policy;
- default `pipeline.py` shape with `fetch`, `clean`, `save`, and `write_receipt` step functions.

This gate keeps API-specific requirements explicit before code lands while avoiding premature four-file bundle sprawl.

## Task Runs

A task key is stable. A scheduled or periodic task may run many times with the same task key. Each invocation is a data task run with its own `run_id`, run output directory, status, row counts, and error evidence.

Development output layout should follow:

```text
data/storage/<task-id>/
  task_key.json
  completion_receipt.json
  runs/
    <run-id>/
      raw/
      cleaned/
      saved/
```

The task-level completion receipt should contain `runs[]` so manager can inspect every run without changing the task key.

## Development Storage Rule

During development, `trading-data` must not write task outputs into SQL by default. Use the registered development local storage root instead:

```text
data/storage/
```

This directory is ignored by Git except for README files. It is intentionally easy to inspect, clear, and recreate. Development outputs, temporary raw responses, cleaned files, manifests, and task receipts should be grouped by stable task id and run id inside this root when implementation begins.

For high-volume raw market data such as trade prints and quote updates, temporary raw segments are only run-local aggregation inputs. Default saved outputs must be aggregate/feature rows aligned to accepted America/New_York time buckets.

SQL writes are future durable-storage behavior and should require an accepted `trading-storage` contract or an explicitly guarded integration/smoke path.

## Historical Acquisition Script Bundles

Initial script boundaries should be organized around data-type bundles:

| Script / bundle | Source | Intended contents | Notes |
|---|---|---|---|
| `alpaca_bars` | Alpaca | Historical stock/ETF bars. | Keep separate because bar retrieval has distinct parameters and table shape. |
| `alpaca_liquidity` | Alpaca | Liquidity bars. | News is intentionally split out because request shape, cadence, and downstream usage differ from market microstructure events. |
| `alpaca_news` | Alpaca | Stock/ETF news. | Standalone bundle for news retrieval, article metadata, source/timestamp handling, and final cleaned news outputs. |
| `thetadata_option_primary_tracking` | ThetaData | One selected primary/main option contract tracked alongside equity bars/liquidity at the same research grain. | Supplements equity bars/liquidity after contract selection; raw trade/quote/NBBO inputs should aggregate into final tracking rows. |
| `thetadata_option_event_timeline` | ThetaData | News-like timeline records for unusual option contract activity. | Event-oriented output, similar to news: timestamped option activity signals rather than bulk raw ticks. |
| `thetadata_option_selection_snapshot` | ThetaData | Point-in-time option-chain snapshot visible at signal/selection time. | Simulates what the strategy could know when choosing a contract; preserve timestamp and visible contract context. |
| `okx_crypto_market_data` | OKX | Historical crypto bars/trades/liquidity. | Quote-derived liquidity fields may be blank when no sampled order-book snapshots exist. |
| `macro_data` | FRED-unique series, Census, BEA, BLS, U.S. Treasury Fiscal Data, official agency pages | Parameterized macro data acquisition. | One macro bundle for clarity; task params must select provider/source, dataset/release/series, cadence, time range, and output target. Do not use FRED to duplicate data whose official source is accepted elsewhere. |
| `calendar_discovery` | Official web sources discovered by search | FOMC and official macro release calendars. | Confirm official source domains before accepting results. |
| `etf_holdings` | ETF issuer websites/files | ETF constituent stocks and weights. | Preserve issuer URL, as-of date, retrieval timestamp, and file format. |

These names are planning names until accepted through registry/contract review.

## Macro Data Bundle Rule

Macro data uses one accepted bundle key: `macro_data`.

This keeps bundle inventory small while moving selection detail into task params. A `macro_data` task must explicitly identify the requested source/provider, dataset or release key, series identifiers when applicable, publication/revision behavior, cadence, covered period or time range, official source URL, and output target.

Examples of valid `macro_data` parameter selections include BLS CPI, BLS employment, BEA GDP, BEA PCE, Census retail sales, Census durable goods, FRED-unique St. Louis Fed/ALFRED/research series, U.S. Treasury Fiscal Data datasets, and official agency release pages.

Do not create a new bundle just because a macro dataset comes from a different agency. Split inside `params`, not in the bundle registry, unless a future implementation proves one source needs a fundamentally different runner boundary.

For source consistency, the same economic measure should have one canonical acquisition source. Use official agency sources for BLS, BEA, Census, Treasury, and other agency-owned data. Use FRED only for data that is unique to FRED/St. Louis Fed/ALFRED or for explicitly approved FRED-native research series/groups, not as a duplicate path for the same official data.

## Completion Receipt Requirements

After each task attempt during development, `trading-data` should write a local completion receipt under `data/storage/`. Once durable contracts are accepted, this receipt can move through `trading-storage`. The receipt should eventually record:

- task key reference and idempotency/replay key;
- selected script/bundle and code version;
- started/completed timestamps;
- status and failure reason when applicable;
- provider/source URLs and credential alias evidence without secret values;
- request parameters actually used;
- development file references and future output SQL table/partition references;
- row counts and validation summary;
- retry/rate-limit evidence;
- references to raw/normalized artifacts or manifests if those contracts are accepted.

The receipt belongs in storage, not Git. Exact status fields and storage placement remain pending contract work.

## Provider Boundary

Each provider integration should document:

- supported markets and instruments;
- authentication and secret alias expectations;
- rate limits and quota behavior;
- timestamp/timezone semantics;
- response completeness limitations;
- retry and backoff policy;
- fixture coverage for expected and edge-case responses.

Provider credentials must not be committed.

## Validation Boundary

Validation should eventually cover:

- required columns and types;
- timestamp monotonicity and timezone handling;
- duplicate rows;
- missing bars/quotes/events relative to market calendars;
- symbol normalization;
- provider-specific null/placeholder values;
- output artifact readability by downstream consumers.

Exact validation schemas are not yet accepted.

## Open Gaps

The following workflow details must be defined before implementation depends on them:

- exact task key file/request schema for data work, including release-event keys for macro tasks;
- request domain classification;
- exact artifact reference format;
- exact manifest schema;
- exact ready-signal schema;
- provider selection and priority rules;
- macro release event inventory and bundle naming rules;
- data-source connector layout and credential alias convention;
- raw vs normalized artifact policy;
- data partitioning strategy;
- fixture storage policy;
- retry/backoff defaults;
- live-provider test policy;
- development-to-durable promotion rule, storage SQL table/partition contract, and shared storage root/path contract.
