# Data Sources

`trading-data` must connect to external and approved local data sources before it can produce cleaned data outputs.

This file defines the source-connection boundary: where provider adapters belong, how credentials are referenced, and what must be documented before a provider can become part of a data domain pipeline.

## Source Layer Purpose

The first implementation layer should be data-source connection and provider adaptation.

It should own:

- provider client setup;
- authentication by secret alias;
- request construction;
- rate-limit and quota handling;
- response capture for normalization;
- provider-specific error handling;
- provider capability documentation;
- fixture or mock coverage for default tests.

It should not own:

- strategy signals;
- model labels or inference;
- execution decisions;
- dashboard presentation;
- durable storage policy;
- provider credentials or secret values.

## Future Source Layout

No source package exists yet. When implementation starts, the first source area should be a provider/source connector layer, with exact package layout accepted before code lands.

A likely Python package shape is:

```text
src/trading_data/
  sources/          Provider adapters and source capability descriptors.
  domains/          Domain assembly for market_board_data, instrument_data, option_data.
  normalize/        Provider-to-output normalization logic.
  validate/         Data quality checks.
  outputs/          Artifact/manifests/ready-signal writers after contracts are accepted.
tests/              Component tests, with README inventory for each test script.
```

Shared helpers belong in `trading-main`, not in a local `helpers/` folder.

This is a planning shape, not an accepted implementation contract. Any final source layout must update docs and tests in the same change.

## Secret And Credential Rule

Provider tokens, API keys, account identifiers, private keys, and credentials must never be committed to this repository.

Credential material belongs outside Git under one source-level JSON file per provider/source:

```text
/root/secrets/<source>.json
```

Shared or reviewed references should be stored as source aliases, not values. When a provider credential becomes a cross-repository or durable config dependency, register a `config` row in `trading-main` whose payload is the source alias and whose `path` mirrors the local source JSON file.

Provider `term` rows may use their `path` field for canonical public documentation URLs. Secret `config` rows keep their `path` field pointed at local source JSON files.

OKX is the first accepted provider config surface for crypto data acquisition and later trading access. Source credentials use one JSON secret file per provider/source. Additional provider aliases remain open until providers are selected.


## Registered Provider And Source Surfaces

Current registered provider config and source-of-truth surfaces:

| Provider | Documentation path | Purpose | Registered config keys | Secret aliases / values | Notes |
|---|---|---|---|---|---|
| OKX | `https://www.okx.com/docs-v5/en/` | Crypto data acquisition and later trading access. | `OKX_SECRET_ALIAS` | source alias `okx`; JSON path `/root/secrets/okx.json`; JSON keys `api_key`, `secret_key`, `passphrase`, `allowed_ip_address`, `api_key_remark_name` | Secret values and credential metadata live in `/root/secrets/okx.json` and must not be copied into this repository. |
| Alpaca | `https://docs.alpaca.markets/` | Stock and ETF bars, quotes, trades, and news data acquisition. | `ALPACA_SECRET_ALIAS` | source alias `alpaca`; JSON path `/root/secrets/alpaca.json`; JSON keys `api_key`, `secret_key`, `endpoint` | Secret values and endpoint config live in `/root/secrets/alpaca.json` and must not be copied into this repository. |
| ThetaData | `https://http-docs.thetadata.us/` | Options chain timeline, quote, trade, OHLC, Greeks, and related options datasets. | `THETADATA_SECRET_ALIAS` | source alias `thetadata`; JSON path `/root/secrets/thetadata.json`; JSON keys include credential fields and entitlement metadata | Secret values and entitlement details live in `/root/secrets/thetadata.json` and must not be copied into this repository. ThetaTerminal JAR/runtime placement is deferred until connector design. |
| FRED | `https://fred.stlouisfed.org/docs/api/fred/` | FRED/St. Louis Fed/ALFRED-unique macro series and explicitly approved FRED-native research series/groups. | `FRED_SECRET_ALIAS` | source alias `fred`; JSON path `/root/secrets/fred.json`; JSON key `api_key` | Secret value lives in `/root/secrets/fred.json` and must not be copied into this repository. Do not use FRED as a duplicate acquisition path for BLS/BEA/Census/Treasury data that has an accepted official source. |
| Census | `https://www.census.gov/data/developers/guidance/api-user-guide.html` | Demographic and economic data acquisition. | `CENSUS_SECRET_ALIAS` | source alias `census`; JSON path `/root/secrets/census.json`; JSON key `api_key` | Secret value lives in `/root/secrets/census.json` and must not be copied into this repository. |
| BEA | `https://apps.bea.gov/API/docs/index.htm` | Economic accounts and macroeconomic data acquisition. | `BEA_SECRET_ALIAS` | source alias `bea`; JSON path `/root/secrets/bea.json`; JSON key `api_key` | Secret value lives in `/root/secrets/bea.json` and must not be copied into this repository. |
| BLS | `https://www.bls.gov/developers/api_signature_v2.htm` | Labor and economic data acquisition. | `BLS_SECRET_ALIAS` | source alias `bls`; JSON path `/root/secrets/bls.json`; JSON key `api_key` | Secret value lives in `/root/secrets/bls.json` and must not be copied into this repository. |
| U.S. Treasury Fiscal Data | `https://fiscaldata.treasury.gov/api-documentation/` | Federal finance datasets including debt, revenue, spending, interest rates, and savings bonds. | None; provider term `US_TREASURY_FISCAL_DATA` is registered. | No secret alias currently; official docs describe the API as open and not requiring a user account or token. | Connector design must still document dataset coverage, pagination, rate/usage behavior, timestamp semantics, and fixture policy. |
| SEC EDGAR | `https://www.sec.gov/search-filings/edgar-application-programming-interfaces` | Public company submissions, XBRL facts, company financial reporting data, and filing metadata. | None; provider term `SEC_EDGAR` and bundle term `SEC_COMPANY_FINANCIALS` are registered. | No credential required; SEC automated access still requires fair-access behavior including an identifying User-Agent. | Preferred bundle key: `sec_company_financials`. Use official SEC endpoints such as company facts and submissions, preserve source filing dates/accession metadata, use America/New_York for research timestamps, and persist only final cleaned outputs. |
| FOMC Calendar | `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm` | FOMC meeting calendar and related monetary policy event information. | None; source term `FOMC_CALENDAR` is registered. | No credential required. | Official Federal Reserve page is the source of truth. Connector work must preserve source URL and retrieval timestamp. |
| Official macro release calendars | Web search to current official agency pages. | Release dates/times for macroeconomic publications relevant to market context. | None; source term `OFFICIAL_MACRO_RELEASE_CALENDAR` is registered. | No general credential rule; use official agency sources. | Use web search for discovery, then confirm official government/issuing-agency domains. Third-party calendars are secondary only unless explicitly approved. |
| ETF issuer holdings | Issuer websites or issuer-published holdings files. | ETF constituent stocks and portfolio weights/proportions. | None; source term `ETF_ISSUER_HOLDINGS` is registered. | Usually no credential; issuer-specific access rules remain open. | Issuer website is the source of truth. Preserve issuer URL, as-of date, retrieval timestamp, holdings file format, and any cash/derivative rows. |

`trading-main` owns provider term rows, documentation paths, source-level aliases, registered JSON key names, and non-secret metadata. `trading-data` may use an alias once implementation has a connector boundary and default tests do not require live credentials.



## Data Kind Registry Rule

Every obtainable data category accepted after source/API availability review should be registered in `trading-main` as `kind=data_kind` before implementation depends on it.

`data_kind` rows are for concrete data categories such as bars, quotes, option Greeks, SEC company facts, CPI, GDP, or Treasury datasets. They are separate from `data_bundle` rows: bundles choose the runner boundary, while data kinds identify what data can be requested, validated, routed, and eventually mapped to storage.

High-volume raw trade and quote kinds are requestable source inputs, not default persisted outputs. For Alpaca liquidity, production persistence should target the ET-aligned aggregate data kind `equity_liquidity_bar`. Raw `equity_trade` and `equity_quote` rows may be streamed or temporarily segmented during a run for aggregation and validation, then discarded unless a bounded debug fixture/incident artifact is explicitly approved.

## Acquisition Script Boundary

Source connector scripts should be split by historical data type and usage bundle so `trading-manager` can freely compose data tasks through task key files. Accepted bundle keys are registered in `trading-main` as `kind=data_bundle`. See `09_api_templates.md` for the required template design gate before implementation. Initial planning boundaries are:

- Alpaca bars: one bars-only script/bundle.
- Alpaca liquidity: one bundle for liquidity bars, excluding news.
- Alpaca news: one standalone bundle for stock/ETF news because request shape, cadence, text/article metadata, and downstream usage differ from liquidity.
- ThetaData option 1-minute bundle: one bundle for `chain_timeline_1m`, `quote_1m`, `trade_1m`, `ohlc_1m`, `greeks_1m`, and `open_interest_1m`.
- ThetaData option snapshot bundle: one separate bundle for requested-time snapshot, open interest, and Greeks.
- OKX bars: one bars-only script/bundle.
- Macro data: one parameterized bundle for FRED-unique series, Census, BEA, BLS, U.S. Treasury Fiscal Data, and official macro source pages; task params select the concrete provider/source, dataset/release/series, cadence, period, and output target.
- Calendar discovery: one web-search-backed source workflow for FOMC and official macro release calendars.
- ETF holdings: one issuer-site/source-file workflow for constituent stocks and weights.
- SEC company financials: one official SEC EDGAR workflow for public-company financial report facts, filings/submissions metadata, and future normalized statement outputs.

These are historical acquisition boundaries. Realtime streaming and execution-time feeds remain out of scope for `trading-data`. Each bundle should start as one `pipeline.py` file with `fetch`, `clean`, `save`, and `write_receipt` functions; split files only when complexity justifies it. Bundle-specific API details belong in the bundle README.

## SEC Company Financials Bundle Rule

The SEC company financials bundle key is `sec_company_financials`.

This bundle should fetch public company financial report data from official SEC EDGAR APIs, starting with company facts and submissions/filing metadata. It should not use third-party SEC mirror APIs as the source of truth unless separately reviewed.

Bundle design must document:

- SEC endpoint URL patterns and CIK/ticker mapping behavior;
- required identifying User-Agent and SEC fair-access/rate-limit behavior;
- requested company identifiers, filing form filters such as 10-K/10-Q, fiscal period/year filters, taxonomy/tag selection, and revision/amendment handling;
- source filing dates, accession numbers, report periods, fiscal year/period fields, and retrieval timestamps;
- timestamp handling in America/New_York for stock-research workflow metadata;
- stable random ID prefixes: `sec_company_financials_task_...` and `sec_company_financials_run_...`;
- segment fetch-clean-save behavior so large company/history ranges can resume without saving bulky raw intermediates;
- final cleaned development outputs only, with durable SQL mapping deferred to storage contracts;
- development-only tiny sanitized SEC response fixtures, removed or replaced with minimal synthetic contract fixtures before production hardening.


## Alpaca News Bundle Rule

News is intentionally separated from Alpaca liquidity market events.

Accepted Alpaca bundle keys are:

- `alpaca_bars` for bars;
- `alpaca_liquidity` for liquidity bars;
- `alpaca_news` for news.

`alpaca_news` must document article timestamps in America/New_York for research workflow metadata, provider publication timestamp semantics, symbols/entities covered, source/publisher fields, pagination, and rate-limit behavior. Task/run IDs should use `alpaca_news_task_...` and `alpaca_news_run_...` prefixes. Development should persist only final cleaned news outputs; tiny sanitized provider response fixtures are allowed only during development and should be replaced before production hardening.

## Macro Data Source Rule

`macro_data` is removed as an executable acquisition bundle. Macro calendar/value rows for model inputs now use `trading_economics_calendar_web` as the accepted source surface.

The Trading Economics path is deliberately constrained:

- visible website calendar rows only;
- no Trading Economics API;
- no Download/export endpoints;
- no WAF/captcha/permission bypass;
- bounded windows, with bulk history deferred until explicitly accepted.

BLS, BEA, Census, Treasury, FRED, and ALFRED API keys/secret aliases may remain registered and stored for future optional research, but manager-issued macro tasks should not use the removed `macro_data` bundle.

## Web-Discovered And Issuer-Sourced Inputs

Some accepted source surfaces are source-of-truth rules rather than credentialed APIs:

- FOMC calendar data should come from the official Federal Reserve FOMC calendar page.
- Macro release calendars should be found through web search, then accepted only after confirming an official government or issuing-agency domain.
- ETF holdings constituents and weights should come from issuer websites or issuer-published holdings files.

For these inputs, connector design must record:

- source URL;
- retrieval timestamp;
- publication, effective, or as-of date when available;
- file/page format;
- whether the source is official primary, official mirror, or approved secondary reference;
- fixture sanitization and live-call guardrails.

## Provider Inventory Template

Each provider added later should document:

| Field | Meaning |
|---|---|
| Provider name | Human-readable provider name. |
| Provider role | Which data domain(s) it supports. |
| Secret alias | Alias path only; never the secret value. |
| Authentication method | Token, API key, OAuth, signed request, local file, etc. |
| Supported instruments | Equities, ETFs, options, indexes, macro series, calendars, etc. |
| Supported ranges/granularity | Time range, bar size, snapshot support, chain history, etc. |
| Rate limits and quotas | Calls/minute, calls/day, paid-plan limits, reset behavior. |
| Timestamp semantics | UTC, exchange local, provider local, timezone fields, market session behavior. |
| Data-quality caveats | Gaps, delays, survivorship risks, stale fields, adjusted/unadjusted behavior. |
| Fixture policy | Whether sample responses may be stored and how they are sanitized. |

## Connection Acceptance Checklist

A provider/source connector is acceptable only when:

- no secret values are committed;
- credentials are referenced by alias;
- provider capabilities and limitations are documented;
- default tests do not require live credentials or network calls;
- rate-limit behavior is documented before automation loops are introduced;
- timestamp and timezone behavior is documented;
- provider response examples are sanitized if fixtures are committed;
- any shared config keys or provider-independent vocabulary are routed through `trading-main`.

## Open Provider Decisions

- Which additional non-OKX/non-economic provider(s), if any, support market board data?
- Which non-Alpaca provider(s), if any, support non-crypto instrument data?
- ThetaData connector/JAR/credential layout for the option data domain.
- Which additional source-level secret aliases should be registered in `trading-main`?
- U.S. Treasury Fiscal Data dataset and endpoint coverage for federal finance context.
- Macro release event inventory, release-key naming, and per-release bundle boundaries.
- FOMC and official macro release calendar discovery/update cadence.
- ETF issuer holdings source coverage, issuer priority, file formats, and as-of-date handling.
- What live-call guardrail is acceptable for manual provider smoke tests?
- Which provider fixtures are safe and useful to commit?
