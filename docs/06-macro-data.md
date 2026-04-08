# 06 Macro Data

This document defines the first-wave macro/economic data contract for `trading-data`.

## Scope

Macro/economic data is treated as a low-frequency context layer, not as market tape.

Current source plan:
- FRED for core historical macro time series
- BLS for labor/inflation official source coverage
- BEA for GDP / spending-side official source coverage
- Census for retail / housing / activity official source coverage
- Treasury Fiscal Data for fiscal/liquidity datasets
- Federal Reserve official webpages / RSS / calendars for policy event timelines

## Storage rule

Use append/upsert full-history files per logical series or dataset.

Examples:
- `context/macro/fred/DGS10.jsonl`
- `context/macro/fred/CPIAUCSL.jsonl`
- `context/macro/bls/CUUR0000SA0.jsonl`
- `context/macro/bea/GDPC1.jsonl`
- `context/macro/census/retail_sales.jsonl`
- `context/macro/treasury/debt_to_penny.jsonl`
- `context/macro/events/fomc_calendar.jsonl`

Do not force low-frequency macro series into symbol/month market-tape partitions.

## Current FRED row contract

Each row in `context/macro/fred/<series>.jsonl` should contain:
- `source`
- `series_id`
- `observation_date`
- `value`
- `realtime_start`
- `realtime_end`

Current behavior:
- full-history backfill first
- later reruns should upsert by `(observation_date, realtime_start, realtime_end)`
- file path is the durable artifact and should remain append/upsert friendly

## Initial recommended core series

- `DFF`
- `DGS2`
- `DGS10`
- `T10Y2Y`
- `CPIAUCSL`
- `CPILFESL`
- `UNRATE`
- `PAYEMS`
- `ICSA`
- `GDPC1`

## Downstream alignment rule

Macro series are expected to be joined to market bars downstream via as-of alignment.
`trading-data` owns acquisition and durable storage; downstream repos own bar-level feature joining.
