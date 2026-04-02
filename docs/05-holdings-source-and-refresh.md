# 05 Holdings Source and Refresh

This document consolidates ETF holdings storage rules, source-path status, and SEC/N-PORT tracking logic.

## ETF holdings storage rule

ETF holdings are context metadata, not minute-level market tape.
They should live under:
- `context/etf_holdings/`

### File rule
Use one file per ETF:
- `context/etf_holdings/<ETF>.json`

### Current normalized schema
Keep only:
- `etf_symbol`
- `as_of_date`
- `constituent_symbol`
- `constituent_name`
- `weight_percent`

### History rule
Do not create a separate `etf_holdings_changes` storage layer.
Keep monthly holdings history inside the ETF's single JSON file and compute changes later when needed.

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

A lightweight local state file will likely be needed, for example:
- `context/etf_holdings/_nport_state.json`

It should track things like:
- `target_month`
- `last_checked_at`
- `current_month_available`
- `current_month_captured`
- `source_reference`
- `notes`

## Current open questions

1. how to map ETF ticker symbols to the relevant fund/series/entity identifiers in N-PORT
2. how to detect that the current month is actually available
3. which exact raw tables are required to reconstruct the compact holdings schema
4. how much raw source material should be retained versus normalized and discarded
