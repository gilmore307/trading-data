# Task

## Active Tasks

- Calibrate and harden the first derived model-input bundles: `stock_etf_exposure` freshness/scoring rules and `equity_abnormal_activity_event` thresholds/model standards.

## Queued Tasks

- Define initial manager-issued data task key file schema with `trading-main` and `trading-manager`.
- Fill API-specific templates for the first implementation bundle before writing connector code.
- Define strict Trading Economics macro calendar task/config vocabulary for accepted visible-page macro model inputs.
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
- Exact source connector package layout beyond the implemented bundle slices.
- Exact bundle invocation contract and runner interface beyond current CLIs.
- Exact development output subdirectory/file layout under `storage/` beyond task/run grouping.
- Exact segment naming/checkpoint/resume evidence format.
- Exact data artifact schema and reference format.
- Exact manifest and ready-signal schema.
- Exact completion receipt durable schema and storage location.
- Exact storage SQL table/partition destination contract for durable/production mode.
- Shared storage root and partition layout.
- Timestamp normalization contract for payload fields that must remain America/New_York versus any required UTC/database fields.
- Provider quota/rate-limit policy and live-call guardrails.
- Source-specific parameter dictionaries for each registered `data_kind`, including which FRED series are truly FRED/St. Louis Fed/ALFRED-native.
- ETF issuer priority list, source-file formats, and as-of-date/available-time handling.
- Production ETF holdings freshness/available-time rules for `stock_etf_exposure`.
- Calibrated `equity_abnormal_activity_event` detection standards, lookbacks, thresholds, and model-standard identity.
- Optionability summary shape for SecuritySelectionModel.
- ThetaData connector/JAR/credential layout.
- Data-domain vocabulary registration in `trading-main` if exact domain keys become cross-repository contract values.

## Recently Accepted

- Implemented `stock_etf_exposure` derived bundle over saved ETF holdings CSV inputs plus caller-supplied ETF/sector/theme scores.
- Implemented `07_bundle_event_overlay/equity_abnormal_activity` derived event detector over saved equity bars, optional benchmark bars, and optional liquidity bars.
- Registered seven model input organization bundles originally; current accepted numbered set has no 04 data bundle, with 06 as position execution and 07 as event overlay.
- Added `stock_etf_exposure` as a derived point-in-time model-input data kind for SecuritySelectionModel.
- Added `equity_abnormal_activity_event` as a derived event-style data kind for EventOverlayModel stock/ETF abnormal price, volume, relative-strength, gap, and liquidity signals.
- Added `docs/11_model_inputs.md` as the current mapping from `trading-source` source outputs and derived products to the seven `trading-model` layer input bundles.
- Implemented `11_source_thetadata_option_event_timeline` for triggered option-activity events: explicit contract + date range + evidence-window `timeframe` + task/model `current_standard` input, local ThetaData Terminal trade_quote endpoint, event-only CSV rows, compact per-event detail JSON artifacts, and no raw provider response persistence.
- Implemented `10_source_thetadata_option_primary_tracking` for specified-contract option bars: explicit contract + date range + `timeframe` input, local ThetaData Terminal OHLC endpoint, zero-volume placeholder filtering, requested-timeframe aggregation, final `option_bar.csv` save, and completion receipt without raw provider response persistence.
- Implemented `09_source_thetadata_option_selection_snapshot` as the first ThetaData option final-output bundle: explicit `underlying` + `snapshot_time` input, local ThetaData Terminal snapshot endpoints, in-memory normalization, atomic final `option_chain_snapshot.json` save, and completion receipt without raw provider response persistence.
- Standardized final saved bundle outputs on CSV only; JSONL may remain a transient cleaned/run-local format but is no longer duplicated into saved outputs.
- Retired the old `storage/templates/data_kinds/` preview catalog after dedicated SQL storage contracts became the accepted data-output boundary.
- Implemented `03_source_alpaca_news` pipeline: fetches Alpaca news with bounded pagination, normalizes article timestamps to America/New_York, and saves cleaned `equity_news` CSV without full raw payload persistence.
- Implemented `01_source_alpaca_bars` pipeline: fetches Alpaca bars with bounded pagination, normalizes timestamps to America/New_York, and saves cleaned `equity_bar` CSV without full raw payload persistence.
- Implemented `02_source_alpaca_liquidity` aggregate-only pipeline: fetches Alpaca trades/quotes as transient inputs, aggregates to America/New_York time buckets, saves one `equity_liquidity_bar` CSV, and writes completion receipts without raw trade/quote persistence.
- Decided raw high-volume Alpaca trade/quote rows must not be persisted by default; `02_source_alpaca_liquidity` should save ET-aligned aggregate/derived outputs and discard transient raw segments after aggregation unless a bounded debug artifact is explicitly approved.
- Added provider/data-kind source interface catalog and smoke runner under `src/source_interfaces/`; live checks now confirm Alpaca equity bars/trades/quotes/snapshots/news, OKX crypto bars/trades/tickers/books, and SEC submissions/companyfacts/companyconcept/frames; ThetaData option endpoint families are cataloged but blocked until local Theta Terminal is reachable.
- Removed the executable `macro_data` official macro API acquisition bundle after accepting Trading Economics visible-page rows as the macro model-input source.
- Added `src/source_availability/` as a bounded smoke-probe package and CLI for source/API availability checks; reports write to ignored `storage/source_availability/` and default tests use mocks/fixtures only.
- Registered the initial source-availability `data_kind` inventory in `trading-main` and documented it in `docs/10_source_availability.md`.
- Constrained FRED usage to FRED/St. Louis Fed/ALFRED-unique data or explicitly approved FRED-native research series/groups; official agency measures use their official sources as canonical.
- Previously consolidated macro acquisition into `macro_data`; this was later superseded by Trading Economics visible-page macro inputs.
- Added `data_bundle` as a registry kind and registered current acquisition bundle keys there.
- Split Alpaca news into standalone `03_source_alpaca_news` and renamed liquidity bundle planning to `02_source_alpaca_liquidity`.
- Added `08_source_sec_company_financials` for official SEC EDGAR company financial report data.
- Confirmed all stock research timestamps use America/New_York unless a later storage contract explicitly requires another representation for a field.
- Clarified stable random `task_id` and `run_id` with bundle-specific prefixes.
- Clarified persistence policy: do not retain bulky raw/intermediate outputs by default; persist final cleaned outputs, with production headed toward SQL.
- Clarified fixture policy: development may use tiny sanitized provider-response fixtures to understand structure; production hardening should remove or replace original-shape fixtures with minimal synthetic/contract fixtures.
- Confirmed and registered all current task key / completion receipt JSON fields through `trading-main`.
- Clarified stable task key versus per-run completion receipt `runs[]` model.
- Recorded runtime JSON minimalism for task key and completion receipt templates.
- Updated bundle implementation guidance to default to one `pipeline.py` file with four internal step functions and bundle-specific README details.
- Added API template application guide for data source bundles and linked `trading-main/templates/data_tasks/`.
- Changed development-stage task outputs from SQL writes to ignored local files under `storage/`.
- Formalized manager-driven historical data task workflow: task key file in, specified historical script executes, development output/receipt files are written under `storage/`, and durable SQL/storage receipts remain future contract work.
- Recorded FOMC calendar, official macro release calendar discovery, and ETF issuer holdings source-of-truth rules.
- Recorded U.S. Treasury Fiscal Data as an open/no-key provider term with documentation path.
- Added provider documentation URLs to data-source planning docs, matching registry provider term paths.
- Recorded FRED, Census, BEA, and BLS as registered economic/macro provider config surfaces using source-level secret aliases.
- Recorded ThetaData as registered provider terminology for option data, with connector/JAR/credential layout deferred.
- Recorded Alpaca as first registered stock/ETF data provider config surface using source-level secret alias `alpaca`.
- Recorded OKX as first registered crypto provider config surface using a `trading-main` source-level secret alias and non-secret metadata.
- Added optional data-organization and data-source docs for source/bundle/output planning and provider connection boundaries.
- Created initial `trading-source` docs spine and repository boundary.
- Added initial `.gitignore` for local environments, generated data, artifacts, logs, and secrets.
