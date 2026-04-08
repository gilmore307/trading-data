# 03 Context Layer and Holdings

This document defines the non-market-tape context layer for `trading-data`, especially macro/economic context preparation plus ETF context preparation and any optional ETF holdings source workflows.

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

Current interpretation rule:
- ETF proxies are retained primarily for market-regime, sector rotation, and industry/thematic divergence analysis
- broad-market ETFs and macro/commodity/crypto proxy ETFs are bar/context-first instruments
- sector and industry/thematic ETFs are also bar/context-first instruments when the goal is to evaluate relative divergence rather than constituent look-through
- N-PORT holdings mapping is no longer part of the active mainline design because it implies a constituent-level dependency the current workflow does not require

## Holdings storage rule

ETF holdings are context metadata, not minute-level market tape.
If N-PORT or another source is used in the future, those holdings snapshots should live under:
- `context/etf_holdings/`

Operational/download/discovery helper artifacts live under:
- `context/etf_holdings/_aux/`

Interpretation rule:
- any ETF holdings source snapshots belong to the permanent context accumulation layer
- they are optional enrichment artifacts rather than a required dependency of the active sector/thematic divergence workflow

## Holdings file rule

If holdings snapshots are retained, group them by month directory and use one file per ETF/month snapshot:
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

Current normalized schema keeps only:
- `etf_symbol`
- `as_of_date`
- `constituent_symbol`
- `constituent_name`
- `weight_percent`

## Mainline ETF analysis rule

The active workflow should treat ETF proxies primarily as retained bar/context instruments.

Current rule:
- sector/thematic regime evaluation should not depend on constituent-level ETF holdings extraction
- do not imply that ETF divergence analysis requires N-PORT-based constituent look-through
- N-PORT-based constituent analysis may be revisited later only if the strategy/modeling workflow explicitly requires constituent exposure analysis

## Source-path status

### Blocked / not operational paths
- `etf.com` direct HTTP fetch blocked by Cloudflare
- `etfdb.com` direct HTTP fetch blocked by Cloudflare
- Finnhub ETF holdings path blocked by current account access
- Alpaca not yet validated as a direct ETF holdings source

### Optional future source path
SEC Form N-PORT remains a possible future authoritative source path for ETF/fund holdings disclosure if constituent-level exposure analysis later becomes necessary.

## Current N-PORT scaffold

Runnable N-PORT utilities exist under `src/data/nport/`, but they are no longer part of the active mainline sector/thematic divergence design.

Current state tracking file:
- `context/etf_holdings/_aux/state/nport_state.json`
