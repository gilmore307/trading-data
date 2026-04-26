# Workflow

## Purpose

This file defines the intended data-production workflow for `trading-data`.

It describes how approved data requests become validated data artifacts, manifests, and ready signals without leaking provider-specific details into downstream repositories.

## Data Production Flow

`trading-data` is a historical-data acquisition component. Realtime feeds, live market streaming, and execution-time data handling belong to `trading-execution` unless a later reviewed contract explicitly re-scopes that boundary.

```text
manager task key file -> validate key -> classify data domain -> select acquisition script -> fetch historical data -> normalize -> validate -> write to specified storage SQL target -> write task completion receipt in storage
```

Where:

- **manager task key file** is the manager-issued request/control file that contains enough information to complete the task without hidden chat context;
- **validate key** checks task identity, schema version, requested script/bundle, required parameters, destination expectations, idempotency key, and credential/source references;
- **classify data domain** maps the task to market board data, instrument data, option data, or a rejected/re-scoped request;
- **select acquisition script** invokes the data-type-specific source script named by the task key;
- **fetch historical data** calls external providers, official web sources, issuer websites, or approved local sources through documented source connectors;
- **normalize** converts provider-specific responses into accepted table-oriented data shapes;
- **validate** checks schema, timestamps, completeness, calendars, duplicates, and provider caveats;
- **write to specified storage SQL target** stores cleaned outputs at the SQL destination named by the task key, subject to `trading-storage` contracts;
- **write task completion receipt** records task status and evidence in storage so `trading-manager` can continue lifecycle routing.

The exact task key file schema, SQL table contract, and completion receipt schema remain cross-repository contract work with `trading-main` and `trading-storage`.

## Collaboration Flow

```mermaid
flowchart TD
  A[trading-manager Creates Data Task Key File] --> B[trading-data Validates Task Key]
  B --> C[Select Historical Acquisition Script]
  C --> D[Resolve Source Metadata and Secret Aliases]
  D --> E[Fetch Historical Source Data]
  E --> F[Normalize Rows]
  F --> G[Validate Dataset]
  G --> H[Write Cleaned Rows to Storage SQL Target]
  H --> I[Write Task Completion Receipt in trading-storage]
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
- Storage SQL targets must follow `trading-storage` contracts once those contracts exist.
- Shared fields, statuses, and type names must come from `trading-main/registry/`.
- Live provider calls should be minimized in tests; prefer fixtures, recorded examples, or provider adapters with controlled mocks.


## Task Key File Requirements

The manager-issued task key file should eventually include at least:

- task identity and schema version;
- requested acquisition script or script bundle;
- target data domain;
- provider/source identifiers;
- symbols, underlyings, ETF identifiers, macro series, calendar scope, or source URLs as applicable;
- historical time range, snapshot timestamp, granularity, timezone, and market/session assumptions;
- source credential aliases or confirmation that no credential is required;
- provider-specific parameters;
- idempotency/replay key;
- storage SQL destination, partition expectations, and overwrite/append policy;
- validation expectations;
- completion receipt destination;
- priority, deadline, cancellation, and retry expectations when manager scheduling supports them.

The task key file is a contract surface, not an implementation shortcut. Its exact schema must be accepted through `trading-main` before code treats it as stable.

## Historical Acquisition Script Bundles

Initial script boundaries should be organized around data-type bundles:

| Script / bundle | Source | Intended contents | Notes |
|---|---|---|---|
| `alpaca_bars` | Alpaca | Historical stock/ETF bars. | Keep separate because bar retrieval has distinct parameters and table shape. |
| `alpaca_market_events` | Alpaca | Quotes, trades, and news. | May fetch together because they are commonly used together; write separable outputs. |
| `thetadata_option_1m_bundle` | ThetaData | `chain_timeline_1m`, `quote_1m`, `trade_1m`, `ohlc_1m`, `greeks_1m`, `open_interest_1m`. | One bundle because these option 1-minute datasets are normally consumed together. |
| `thetadata_option_snapshot_bundle` | ThetaData | Snapshot, open interest, and Greeks at a specified timestamp. | Separate from the 1-minute bundle because request shape and use case differ. |
| `okx_bars` | OKX | Historical crypto bars. | Current OKX scope is bars only. |
| `macro_release_bundle` | FRED, Census, BEA, BLS, Treasury, official agency pages | Macro datasets that are published or consumed together. | Preserve release/revision/vintage evidence where available. |
| `calendar_discovery` | Official web sources discovered by search | FOMC and official macro release calendars. | Confirm official source domains before accepting results. |
| `etf_holdings` | ETF issuer websites/files | ETF constituent stocks and weights. | Preserve issuer URL, as-of date, retrieval timestamp, and file format. |

These names are planning names until accepted through registry/contract review.

## Completion Receipt Requirements

After each task attempt, `trading-data` should write a completion receipt through `trading-storage`. The receipt should eventually record:

- task key reference and idempotency/replay key;
- selected script/bundle and code version;
- started/completed timestamps;
- status and failure reason when applicable;
- provider/source URLs and credential alias evidence without secret values;
- request parameters actually used;
- output SQL table/partition references;
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

- exact task key file/request schema for data work;
- request domain classification;
- exact artifact reference format;
- exact manifest schema;
- exact ready-signal schema;
- provider selection and priority rules;
- data-source connector layout and credential alias convention;
- raw vs normalized artifact policy;
- data partitioning strategy;
- fixture storage policy;
- retry/backoff defaults;
- live-provider test policy;
- storage SQL table/partition contract and shared storage root/path contract.
