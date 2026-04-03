# 04 Context and Holdings Layer

This document defines the non-market-tape context layer for `trading-data`, especially ETF context preparation and ETF holdings workflows.

## Underlying-first rule

The primary downstream research/trading object is the underlying.
Options are primarily a context/signal-enrichment layer rather than the immediate main trading object.

## Main object layers

### 1. Underlying layer
Examples:
- stocks
- ETFs
- BTC-related ETFs and other equity-market proxies

### 2. ETF/context layer
Examples:
- broad-market ETFs
- sector ETFs
- thematic ETFs
- cross-asset proxy ETFs

Important direction:
- for a stock underlying, also prepare the sector ETF/context layer that represents the underlying's industry or sector environment
- prepare broad market context via major index-tracking ETFs or equivalent tradable proxies

### 3. Options-context layer
Examples:
- option contract metadata
- open interest
- option volume
- option quotes
- option trades
- option snapshots
- strike / expiry structure

## Candidate ETF-context discovery vs relevance modeling

`trading-data` should prepare:
- candidate ETF/context mappings
- broad-market proxy candidates
- sector/thematic ETF candidate sets for each underlying where useful
- the raw data needed to compare an underlying against those ETF candidates

`trading-model` should later do:
- relevance scoring
- context-model construction
- final usefulness evaluation

## ETF context universe

Current category structure:
- core broad market
- core sector
- macro / commodity / crypto proxy
- industry / sub-industry
- thematic / high-attention
- resource / transition

Machine-readable configs:
- `config/etf_context_universe.json`
- `config/underlying_etf_context_candidates.json`
- `config/etf_holdings_target_universe.json`

Target-universe note:
- `etf_context_universe.json` is the broad candidate context universe
- `etf_holdings_target_universe.json` is the narrower actionable holdings-extraction target list derived from it

## Holdings storage rule

ETF holdings are context metadata, not minute-level market tape.
They should live under:
- `context/etf_holdings/`

Operational/download/discovery helper artifacts should live under:
- `context/etf_holdings/_aux/`

The final ready-to-use downstream constituent artifact should be built separately per researched symbol under:
- `context/constituent_etf_deltas/<SYMBOL>.md`

## Holdings file rule

Group ETF holdings by month directory and use one file per ETF/month snapshot:
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

Current normalized schema keeps only:
- `etf_symbol`
- `as_of_date`
- `constituent_symbol`
- `constituent_name`
- `weight_percent`

## Priority target-universe rule

The holdings pipeline should not try to solve the full ETF universe at once.
Use the actionable priority target list at:
- `config/etf_holdings_target_universe.json`

## Source-path status

### Blocked / not operational paths
- `etf.com` direct HTTP fetch is blocked by Cloudflare
- `etfdb.com` direct HTTP fetch is blocked by Cloudflare
- Finnhub `/etf/holdings` is not accessible with the currently tested account permissions
- Alpaca has not been validated as a direct ETF holdings source

### Candidate authoritative path
SEC Form N-PORT is currently the most serious candidate authoritative source path for ETF/fund holdings disclosure.

## Current N-PORT scaffold

First runnable N-PORT-related utilities now exist under `src/data/nport/`, including discovery, mapping, extraction, normalization, and monthly-output build helpers.

Current known state:
- latest discovered quarterly package: `2025q4_nport.zip`
- latest package metadata files are staged under `context/etf_holdings/_nport_packages/2025q4_nport/`
- quarterly package table layout has been validated against expected TSV members

## Polling / refresh rule

Because N-PORT availability may lag and the exact monthly availability date may not be known in advance:
- check once per day while the target month has not yet been captured
- stop checking for that month once capture succeeds
- resume for the next target month when the calendar rolls forward

State tracking file:
- `context/etf_holdings/_nport_state.json`

## Current open questions

1. how to map ETF ticker symbols to the relevant fund/series/entity identifiers in N-PORT
2. how to detect that the current month is actually available with a stronger package-level signal
3. which exact raw tables are required to reconstruct the compact holdings schema
4. how much raw source material should be retained versus normalized and discarded
