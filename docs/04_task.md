# Task

## Active Tasks

- None.

## Queued Tasks

- Define initial manager-issued data task key file schema with `trading-main` and `trading-manager`.
- Fill API-specific templates for the first implementation bundle before writing connector code.
- Define strict `macro_data` parameter vocabulary and validation rules using registered `data_kind` rows for source, dataset/release/series, cadence, period, revision/vintage behavior, and output target.
- Define bundle-specific task/run ID prefix rules in implementation helpers.
- Define segment checkpoint/resume behavior for long historical fetch-clean-save jobs.
- Define data artifact reference and manifest requirements with `trading-main` and `trading-storage`.
- Define storage-resident data task completion receipt schema with `trading-main` and `trading-storage`.
- Define storage SQL table/partition contract for data-task outputs before durable/production mode.
- Define provider quota/rate-limit/retry policy per source before automation loops are introduced.
- Define ThetaData connector, ThetaTerminal JAR, and creds.txt placement policy.
- Define any additional provider secret alias names through `trading-main` once providers are selected.

## Open Gaps

- Exact manager task key file/request schema beyond the current minimal template.
- Exact source connector package layout.
- Exact bundle invocation contract and runner interface.
- Exact development output subdirectory/file layout under `data/storage/` beyond task/run grouping.
- Exact segment naming/checkpoint/resume evidence format.
- Exact data artifact schema and reference format.
- Exact manifest and ready-signal schema.
- Exact completion receipt durable schema and storage location.
- Exact storage SQL table/partition destination contract for durable/production mode.
- Shared storage root and partition layout.
- Timestamp normalization contract for payload fields that must remain America/New_York versus any required UTC/database fields.
- Provider quota/rate-limit policy and live-call guardrails.
- First supported implementation bundle, market/instrument/granularity, and acceptance path.
- Source-specific parameter dictionaries for each registered `data_kind`, including which FRED series are truly FRED/St. Louis Fed/ALFRED-native.
- ETF issuer priority list, source-file formats, and as-of-date handling.
- ThetaData connector/JAR/credential layout.
- Data-domain vocabulary registration in `trading-main` if exact domain keys become cross-repository contract values.

## Recently Accepted

- Added `docs/11_data_kind_catalog.md` as the concrete data-kind catalog separate from bundle docs; populated Alpaca bars, trades, quotes, derived aggregates, snapshot, and news with source/bundle/status/persistence/range/timestamp/preview details.
- Implemented `alpaca_news` pipeline: fetches Alpaca news with bounded pagination, normalizes article timestamps to America/New_York, and saves cleaned `equity_news` JSONL/CSV without full raw payload persistence.
- Implemented `alpaca_bars` pipeline: fetches Alpaca bars with bounded pagination, normalizes timestamps to America/New_York, and saves cleaned `equity_bar` JSONL/CSV without full raw payload persistence.
- Implemented `alpaca_quotes_trades` aggregate-only pipeline: fetches Alpaca trades/quotes as transient inputs, aggregates to America/New_York time buckets, saves `equity_trade_bar_derived`, `equity_quote_bar_derived`, and `equity_microstructure_bar_derived` JSONL/CSV, and writes completion receipts without raw trade/quote persistence.
- Decided raw high-volume Alpaca trade/quote rows must not be persisted by default; `alpaca_quotes_trades` should save ET-aligned aggregate/derived outputs and discard transient raw segments after aggregation unless a bounded debug artifact is explicitly approved.
- Added provider/data-kind source interface catalog and smoke runner under `src/trading_data/source_interfaces/`; live checks now confirm Alpaca equity bars/trades/quotes/snapshots/news, OKX crypto bars/trades/tickers/books, and SEC submissions/companyfacts/companyconcept/frames; ThetaData option endpoint families are cataloged but blocked until local Theta Terminal is reachable.
- Added the first API-backed `macro_data` acquisition bundle under `src/trading_data/data_sources/macro_data/`; it runs real bounded requests for BLS, Census, BEA, U.S. Treasury Fiscal Data, and FRED, normalizes rows, saves cleaned JSONL/CSV development outputs, and writes completion receipts without persisting full raw provider payloads by default.
- Added `src/trading_data/source_availability/` as a bounded smoke-probe package and CLI for source/API availability checks; reports write to ignored `data/storage/source_availability/` and default tests use mocks/fixtures only.
- Registered the initial source-availability `data_kind` inventory in `trading-main` and documented it in `docs/10_source_availability.md`.
- Constrained FRED usage to FRED/St. Louis Fed/ALFRED-unique data or explicitly approved FRED-native research series/groups; official agency measures use their official sources as canonical.
- Consolidated macro acquisition into one accepted `macro_data` bundle with source/dataset/release/series selection in task params.
- Added `data_bundle` as a registry kind and registered current acquisition bundle keys there.
- Split Alpaca news into standalone `alpaca_news` and renamed quote/trade bundle planning to `alpaca_quotes_trades`.
- Added `sec_company_financials` for official SEC EDGAR company financial report data.
- Confirmed all stock research timestamps use America/New_York unless a later storage contract explicitly requires another representation for a field.
- Clarified stable random `task_id` and `run_id` with bundle-specific prefixes.
- Clarified persistence policy: do not retain bulky raw/intermediate outputs by default; persist final cleaned outputs, with production headed toward SQL.
- Clarified fixture policy: development may use tiny sanitized provider-response fixtures to understand structure; production hardening should remove or replace original-shape fixtures with minimal synthetic/contract fixtures.
- Confirmed and registered all current task key / completion receipt JSON fields through `trading-main`.
- Clarified stable task key versus per-run completion receipt `runs[]` model.
- Recorded runtime JSON minimalism for task key and completion receipt templates.
- Updated bundle implementation guidance to default to one `pipeline.py` file with four internal step functions and bundle-specific README details.
- Added API template application guide for data source bundles and linked `trading-main/templates/data_tasks/`.
- Changed development-stage task outputs from SQL writes to ignored local files under `data/storage/`.
- Formalized manager-driven historical data task workflow: task key file in, specified historical script executes, development output/receipt files are written under `data/storage/`, and durable SQL/storage receipts remain future contract work.
- Recorded FOMC calendar, official macro release calendar discovery, and ETF issuer holdings source-of-truth rules.
- Recorded U.S. Treasury Fiscal Data as an open/no-key provider term with documentation path.
- Added provider documentation URLs to data-source planning docs, matching registry provider term paths.
- Recorded FRED, Census, BEA, and BLS as registered economic/macro provider config surfaces using source-level secret aliases.
- Recorded ThetaData as registered provider terminology for option data, with connector/JAR/credential layout deferred.
- Recorded Alpaca as first registered stock/ETF data provider config surface using source-level secret alias `alpaca`.
- Recorded OKX as first registered crypto provider config surface using a `trading-main` source-level secret alias and non-secret metadata.
- Added optional data-domain and data-source docs for the three data/model lanes and provider connection boundary.
- Created initial `trading-data` docs spine and repository boundary.
- Added initial `.gitignore` for local environments, generated data, artifacts, logs, and secrets.
