# 03 Context Layer and Holdings

This document defines the non-market-tape context layer for `trading-data`, especially macro/economic context preparation plus ETF proxy context preparation.

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
- `trading-storage/1_market_regime/0_permanent/`

Current structure preference:
- `trading-storage/1_market_regime/0_permanent/1_macro/fred/<series>.jsonl`
- `trading-storage/1_market_regime/0_permanent/1_macro/bls/<series>.jsonl`
- `trading-storage/1_market_regime/0_permanent/1_macro/bea/<series>.jsonl`
- `trading-storage/1_market_regime/0_permanent/1_macro/census/<series>.jsonl`
- `trading-storage/1_market_regime/0_permanent/1_macro/treasury/<dataset>.jsonl`
- `trading-storage/1_market_regime/0_permanent/7_events_and_calendars/*.jsonl`

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
- `config/etf_proxy_universe.json`

Current interpretation rule:
- ETF proxies are retained primarily for market-regime, sector rotation, and industry/thematic divergence analysis
- broad-market ETFs and macro/commodity/crypto proxy ETFs are bar/context-first instruments
- sector and industry/thematic ETFs are also bar/context-first instruments when the goal is to evaluate relative divergence

## Mainline ETF analysis rule

The active workflow should treat ETF proxies primarily as retained bar/context instruments.

Current rule:
- sector/thematic regime evaluation should not depend on constituent-level ETF look-through
- ETF divergence analysis is driven by the ETFs' own retained market/context data

## Source-path status

### Blocked / not operational paths
- `etf.com` direct HTTP fetch blocked by Cloudflare
- `etfdb.com` direct HTTP fetch blocked by Cloudflare
- Finnhub ETF holdings path blocked by current account access
- Alpaca not yet validated as a direct ETF holdings source
