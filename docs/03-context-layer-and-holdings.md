# 03 Context Layer and Holdings

This document defines the non-market-tape context layer for `trading-data`, especially macro/economic context preparation plus ETF context preparation and ETF holdings workflows.

## Underlying-first rule

The primary downstream research/trading object is the underlying.
Options are primarily a context/signal-enrichment layer rather than the immediate main trading object.

## Main object layers

### 1. Underlying layer
Examples:
- stocks
- ETFs
- BTC-related ETFs and other equity-market proxies

### 2. Macro/economic context layer
Examples:
- interest-rate series
- inflation series
- labor-market series
- GDP / growth series
- retail / housing / activity series
- Treasury fiscal/liquidity datasets
- official macro event calendars and release timestamps

### 3. ETF/context layer
Examples:
- broad-market ETFs
- sector ETFs
- thematic ETFs
- cross-asset proxy ETFs

### 4. Options-context layer
Examples:
- option contract metadata
- open interest
- option volume
- option quotes
- option trades
- option snapshots
- strike / expiry structure

## Macro/economic context storage rule

Macro/economic context should live under:
- `context/macro/`

Current structure preference:
- `context/macro/fred/<series>.jsonl`
- `context/macro/bls/<series>.jsonl`
- `context/macro/bea/<series>.jsonl`
- `context/macro/census/<series>.jsonl`
- `context/macro/treasury/<dataset>.jsonl`
- `context/macro/events/*.jsonl`

Design rule:
- these datasets are low-frequency context artifacts rather than market tape
- prefer one append/upsert file per series/dataset instead of month-partitioned symbol-style storage
- full-history backfill first, periodic append later

## Candidate ETF-context discovery vs relevance modeling

`trading-data` should prepare:
- candidate ETF/context mappings
- broad-market proxy candidates
- sector/thematic ETF candidate sets
- raw data needed to compare an underlying against those ETF candidates

`trading-model` should later do:
- relevance scoring
- context-model construction
- final usefulness evaluation

## ETF context universe

Current machine-readable configs:
- `config/etf_context_universe.json`
- `config/underlying_etf_context_candidates.json`
- `config/etf_holdings_target_universe.json`

## Holdings storage rule

ETF holdings are context metadata, not minute-level market tape.
They should be treated as a permanent context accumulation path rather than as market-tape partitions.
They live under:
- `context/etf_holdings/`

Operational/download/discovery helper artifacts live under:
- `context/etf_holdings/_aux/`

The final ready-to-use downstream constituent artifact is built under:
- `context/constituent_etf_deltas/<SYMBOL>.md`

Interpretation rule:
- N-PORT holdings are month-scoped context snapshots, but the retained storage family is still a permanent context layer
- this means they belong with append/upsert context accumulation under `context/`, not with the `data/<symbol>/<YYMM>/` market-tape contract

## Holdings file rule

Group ETF holdings by month directory and use one file per ETF/month snapshot:
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

Current normalized schema keeps only:
- `etf_symbol`
- `as_of_date`
- `constituent_symbol`
- `constituent_name`
- `weight_percent`

## Direct constituent-context build rule

ETF month construction is owned at the month scope, but the retained downstream-facing derivative should be the constituent ETF context output rather than a separate reverse symbol map artifact.

For each target month, the N-PORT pipeline should:
- extract holdings for the full actionable ETF target list
- build the month-level ETF outputs under `context/etf_holdings/<YYMM>/`
- build/update downstream-ready constituent ETF context outputs directly from those holdings

Current rule:
- do not treat a reverse symbol map as a required retained artifact
- the active pipeline should build constituent ETF context outputs directly from the retained month holdings outputs
- if a temporary reverse lookup is ever used internally during construction, it should remain an implementation detail rather than a durable storage contract

## Source-path status

### Blocked / not operational paths
- `etf.com` direct HTTP fetch blocked by Cloudflare
- `etfdb.com` direct HTTP fetch blocked by Cloudflare
- Finnhub ETF holdings path blocked by current account access
- Alpaca not yet validated as a direct ETF holdings source

### Candidate authoritative path
SEC Form N-PORT is currently the most serious candidate authoritative source path for ETF/fund holdings disclosure.

## Current N-PORT scaffold

Runnable N-PORT utilities now exist under `src/data/nport/`, including discovery, mapping, extraction, normalization, and monthly-output build helpers.

Current state tracking file:
- `context/etf_holdings/_aux/state/nport_state.json`
