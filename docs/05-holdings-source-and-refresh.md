# 05 Holdings Source and Refresh

This document consolidates ETF holdings storage rules, source-path status, and SEC/N-PORT tracking logic.

## ETF holdings storage rule

ETF holdings are context metadata, not minute-level market tape.
They should live under:
- `context/etf_holdings/`

## Priority target-universe rule

The holdings pipeline should not try to solve the full ETF universe at once.
Use the actionable priority target list at:
- `config/etf_holdings_target_universe.json`

This target list is derived from the broader ETF context universe and defines the first ETF set that `trading-data` should try to cover durably.

### File rule
Group ETF holdings by month directory and use one file per ETF/month snapshot:
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

Examples:
- `context/etf_holdings/2603/QQQ_2603.md`
- `context/etf_holdings/2603/IVV_2603.md`
- `context/etf_holdings/2603/SPY_2603.md`

### Current normalized schema
Keep only:
- `etf_symbol`
- `as_of_date`
- `constituent_symbol`
- `constituent_name`
- `weight_percent`

### History rule
Do not create a separate `etf_holdings_changes` storage layer.
Monthly history should come from the month-partitioned ETF snapshot files themselves. Compute changes later when needed.

### Update cadence
ETF holdings are a low-frequency context layer.
Current intended update cadence: monthly.

## Current source-path status

### Blocked / not operational paths
- `etf.com` direct HTTP fetch is blocked by Cloudflare
- `etfdb.com` direct HTTP fetch is blocked by Cloudflare
- Finnhub `/etf/holdings` is not accessible with the currently tested account permissions
- Alpaca has not been validated as a direct ETF holdings source

### Candidate authoritative path
SEC Form N-PORT is currently the most serious candidate authoritative source path for ETF/fund holdings disclosure.

## What N-PORT appears to provide

Based on public SEC search results and visible descriptions, N-PORT appears to provide:
- fund/ETF reported holdings data
- identifiers for holdings
- fund-level variable/index information
- bulk/packaged data sets rather than lightweight symbol-level holdings API responses

Relevant discovered table/object names include:
- `FUND_REPORTED_HOLDING`
- `IDENTIFIERS`
- `FUND_VAR_INFO`

## Polling / refresh rule

Because N-PORT availability may lag and the exact monthly availability date may not be known in advance:
- check once per day while the current month has not yet been captured
- stop checking for that month once the month is confirmed captured
- resume for the next target month when the calendar rolls forward

## State tracking rule

A lightweight local state file is now defined at:
- `context/etf_holdings/_nport_state.json`

It should track at least:
- `target_month`
- `last_checked_at`
- `current_month_available`
- `current_month_captured`
- `source_reference`
- `notes`

Current intended monthly availability signal:
- if the target month is not yet represented in the source-discovery path, keep `current_month_available=false`
- once the target month is visible in the source path, flip `current_month_available=true`
- only set `current_month_captured=true` after normalized holdings for that target month have been successfully captured

## Current implementation scaffold

First runnable N-PORT-related utilities now exist under `src/data/common/`:
- `check_nport_availability.py` — updates `_nport_state.json` using a coarse SEC dataset-page token check for the target month
- `discover_nport_dataset.py` — discovers available quarterly N-PORT zip packages from the SEC dataset page and records them in `_nport_discovery.json`
- `download_nport_metadata.py` — downloads metadata/readme files from the latest discovered quarterly package into `_nport_packages/`
- `map_etf_to_sec_series.py` — builds candidate ETF -> SEC series matches
- `extract_series_holdings_from_nport.py` — low-memory streaming extraction of ETF-specific candidate holdings from the quarterly package
- `normalize_nport_holdings.py` — normalizes holdings-like raw/candidate records into the compact ETF holdings schema
- `build_etf_holdings_targets.py` — derives the actionable priority ETF holdings target list from the broader ETF context universe
- `update_etf_holdings_from_nport.py` — pipeline runner that executes discovery + mapping + extraction for the configured ETF target list

Current known discovered package state:
- latest discovered quarterly package: `2025q4_nport.zip`
- latest package metadata files are now staged under `context/etf_holdings/_nport_packages/2025q4_nport/`
- quarterly package table layout has been validated against the expected TSV members including `FUND_REPORTED_INFO.tsv`, `FUND_REPORTED_HOLDING.tsv`, and `IDENTIFIERS.tsv`

Current extraction progress:
- low-memory streaming extraction is now implemented in `extract_series_holdings_from_nport.py`
- candidate SEC series mapping is now implemented in `map_etf_to_sec_series.py` using name-pattern candidates from `config/etf_sec_series_candidates.json`
- current month-partitioned sample outputs have been reorganized under `context/etf_holdings/2603/`
- `IVV` is currently the cleanest verified extraction path
- `IWM` also has a clean candidate `SERIES_ID` match in the latest quarterly package
- `QQQ` is now extractable via a `SERIES_LEI` fallback path
- `SPY`, `VOO`, `VTI`, and `DIA` are not yet resolved in the current quarterly package using the present name-pattern mapping approach

Current limitations of this scaffold:
- availability detection is still coarse and page-based rather than a filing/package-level detector
- ETF ticker -> fund/series/entity mapping is only partially resolved
- some flagship ETFs do not currently resolve cleanly via simple name-pattern matching in the latest quarterly package
- extraction currently targets quarterly package parsing and candidate output generation, but not yet the final authoritative per-ETF monthly holdings workflow

## Current open questions

1. how to map ETF ticker symbols to the relevant fund/series/entity identifiers in N-PORT
2. how to detect that the current month is actually available with a stronger package-level signal
3. which exact raw tables are required to reconstruct the compact holdings schema
4. how much raw source material should be retained versus normalized and discarded
