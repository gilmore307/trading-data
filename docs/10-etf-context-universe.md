# 10 ETF Context Universe

This document records the first explicit ETF context universe for `trading-data`.

The purpose is not to claim the final downstream relevance model is complete.
The purpose is to establish a stable upstream candidate ETF set that the data layer should be prepared to support.

## Broad market ETFs

Core broad-market context symbols currently prioritized:
- `SPY`
- `IVV`
- `VOO`
- `QQQ`
- `DIA`
- `IWM`

These provide broad market, large-cap growth, Dow, and small-cap context.

## Sector ETFs

Current sector ETF set:
- `XLK` — technology
- `XLF` — financials
- `XLE` — energy
- `XLI` — industrials
- `XLV` — healthcare
- `XLY` — consumer discretionary
- `XLP` — consumer staples
- `XLU` — utilities
- `XLB` — materials
- `XLRE` — real estate
- `XLC` — communication services

## Thematic / special context ETFs

Current thematic/special context set:
- `SMH`
- `SOXX`
- `XBI`
- `IBB`
- `ARKK`
- `IBIT`
- `FBTC`
- `BITB`

## Config file

The current machine-readable ETF context universe is stored at:
- `config/etf_context_universe.json`

## Current role

This ETF universe is the candidate context pool.
`trading-data` should be prepared to support data collection for these context objects.
`trading-model` can later evaluate which of them are actually most informative for a given underlying.
