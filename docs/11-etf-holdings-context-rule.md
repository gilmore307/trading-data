# 11 ETF Holdings Context Rule

This document defines how ETF holdings context should be stored in `trading-data`.

## Core rule

ETF holdings are context metadata, not minute-level market tape.
They should live under:
- `context/etf_holdings/`

## File rule

Use one file per ETF:
- `context/etf_holdings/<ETF>.json`

Examples:
- `context/etf_holdings/SPY.json`
- `context/etf_holdings/QQQ.json`
- `context/etf_holdings/XLK.json`

## Update frequency

ETF holdings should be treated as a low-frequency context layer.
The current intended update cadence is monthly.

## Scope rule

Do not attempt to store all ETFs by default.
Only maintain holdings for the approved ETF context universe.

## Keep only the core fields

The current normalized holdings layer should keep only:
- `etf_symbol`
- `as_of_date`
- `constituent_symbol`
- `constituent_name`
- `weight_percent`

This is the minimum useful schema for:
- ETF -> holdings lookup
- stock -> candidate ETF reverse mapping
- weight-based context ranking
- later relevance modeling downstream

## History rule

Do not create a separate `etf_holdings_changes` storage layer.
Instead:
- keep monthly holdings history inside the ETF's single JSON file
- calculate additions/removals/weight changes later by comparing monthly entries when needed

This keeps the storage model simpler and avoids maintaining redundant derivative files too early.

## Interpretation rule

ETF holdings are relatively static compared with minute-level market data.
However, month-over-month changes may still be meaningful context signals because they can reflect:
- exposure shifts
- index/ETF rebalance effects
- constituent additions/removals
- changing weight concentration

So the raw storage remains simple, while the change interpretation can happen downstream when needed.
