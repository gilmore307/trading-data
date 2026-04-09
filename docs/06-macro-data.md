# 06 Macro Data

This document defines the permanent macro/economic context layer for `trading-data`.

## Scope

Macro/economic data is treated as a low-frequency context layer, not as market tape.

## Storage rule

Use canonical permanent context files under `context/macro/`.

Examples:
- `context/macro/fred/DGS10.jsonl`
- `context/macro/fred/CPIAUCSL.jsonl`
- `context/macro/bls/CUUR0000SA0.jsonl`
- `context/macro/bea/GDPC1.jsonl`
- `context/macro/census/retail_sales.jsonl`
- `context/macro/treasury/debt_to_penny.jsonl`

Design rule:
- prefer one durable append/upsert file per logical series or dataset
- do not force low-frequency context data into market-tape-style month partitions
- preserve source/native frequency rather than fabricating synthetic bar contracts by default
- when used downstream with higher-frequency market data, treat the latest released observation as the active known value until the next official release replaces it

## Current source families

### FRED
Supported via:
- `src/data/macro/fetch_fred_series.py`

Use for:
- rates / curve
- inflation
- labor / growth
- selected broad macro state inputs

### BLS
Supported via:
- `src/data/macro/fetch_bls_series.py`

Use for:
- inflation and labor-market source series where BLS is the authoritative publisher

### BEA
Supported via:
- `src/data/macro/fetch_bea_series.py`

Use for:
- GDP and related national accounts series

### Census
Supported via:
- `src/data/macro/fetch_census_series.py`

Use for:
- retail / housing / activity datasets where Census is the authoritative publisher

### Treasury Fiscal Data
Supported via:
- `src/data/macro/fetch_treasury_dataset.py`

Use for:
- fiscal / debt / liquidity-related official datasets

### Federal Reserve official calendars
Supported via:
- `src/data/macro/build_fomc_calendar.py`

Use for:
- FOMC meeting calendar maintenance
- policy-event scheduling context

## Economic-event schema rule

For scheduled macro/economic events, model the data in two layers rather than one blended object.

### 1. Calendar / expectation layer
This is the pre-release layer used for scheduling and expectation-aware research.

Preferred fields include:
- `event_id`
- `dataset_id`
- `series_id`
- `release_period`
- `plan_at`
- `forecast` / `expected`
- `previous`
- `importance`
- `calendar_source`
- `notes`

### 2. Release result / actual layer
This is the post-release layer used for surprise analysis and realized-event research.

Preferred fields include:
- `event_id`
- `dataset_id`
- `series_id`
- `release_period`
- `released_at`
- `actual`
- `previous`
- `revised_previous`
- `result_source`
- `release_status`
- `notes`

Design rule:
- the calendar layer should answer "what is scheduled / expected"
- the result layer should answer "what was actually released"
- downstream surprise analysis should compare `actual` against `forecast`/`expected` while preserving revision context

## Operational rule

These macro datasets should be refreshed as permanent context artifacts.
They are not symbol/month market-data partitions.

Manager-side scheduling should prefer:
- official release-calendar-driven refresh for datasets with clear release timestamps
- lower-frequency ET-based polling only where a precise maintained calendar is not yet available

Current executable-ledger direction:
- `trading-storage/1_market_regime/0_permanent/0_task_status/release_dataset_refresh_tasks.csv` is the human-facing ordered task ledger for regime-side release/calendar refresh work
- calendar refresh is treated as a normal task family inside that ledger rather than as a separate scheduler table
- a first maintained calendar builder now exists at `src/data/macro/build_official_macro_release_calendar.py` and writes `trading-storage/1_market_regime/0_permanent/7_events_and_calendars/official_us_macro_release_calendar.jsonl`
- a first search-backed fallback builder now also exists at `src/data/macro/build_official_macro_release_calendar_via_search.py` and writes `official_us_macro_release_calendar.search_fallback.jsonl` with explicit source provenance fields
- intended source priority for `official_us_core` is: official/source-backed parser first, search-backed fallback second, maintained fallback last
- Brave search may be used for calendar-coverage fallback when official parsing is weak, but it should be used sparingly and in batched discovery mode rather than as a high-frequency polling layer
- manager can read the maintained calendar artifact and generate future `macro_release` tasks from it
- tasks may use `plan_at` as the earliest eligible execution timestamp
- if `plan_at` is blank, the task may start immediately
- if `plan_at` is in the future, manager should wait until that timestamp
- once `plan_at` has passed, failed tasks remain eligible on later scans only when their retry policy permits it
- when populated, `plan_at` should be a full ET timestamp rather than a date-only shortcut
