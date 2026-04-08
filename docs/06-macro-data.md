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

## Operational rule

These macro datasets should be refreshed as permanent context artifacts.
They are not symbol/month market-data partitions.

Manager-side scheduling should prefer:
- official release-calendar-driven refresh for datasets with clear release timestamps
- lower-frequency ET-based polling only where a precise maintained calendar is not yet available
