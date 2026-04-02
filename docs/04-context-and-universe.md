# 04 Context and Universe

This document consolidates the context-layer and universe-support rules for `trading-data`.

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
- prepare broad market context via major index-tracking ETFs or equivalent tradable proxies such as Nasdaq / S&P 500 / Dow / Russell 2000 related instruments

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

### Broad market core
- `SPY`, `VOO`, `IVV`, `VTI`, `QQQ`, `IWM`, `DIA`

### Core sector
- `XLK`, `XLF`, `XLE`, `XLV`, `XLI`, `XLY`, `XLP`, `XLB`, `XLU`, `XLRE`, `XLC`

### Macro / commodity / crypto proxy
- `GLD`, `IAU`, `SLV`, `USO`, `DBC`, `PDBC`, `IBIT`, `ETHA`, `FSOL`, `BITW`

### Important industry / sub-industry
- `SMH`, `SOXX`
- `IGV`, `CLOU`, `BUG`
- `XBI`, `IBB`, `IHI`, `IHF`, `XHE`, `XHS`, `IHE`
- `KRE`, `IAT`, `KBE`, `KIE`, `IAI`
- `ITA`, `IYT`
- `XHB`, `XRT`, `XME`, `XOP`, `XES`, `IEO`, `IEZ`

### Thematic / high-attention
- `AIQ`, `BOTZ`, `DTCR`, `DRIV`
- `FINX`, `ARKF`, `BKCH`
- `ARKG`, `ARKW`, `HERO`, `SOCL`, `EBIZ`, `ARKX`

### Resource / transition
- `LIT`, `NLR`, `REMX`, `GDX`

Machine-readable config:
- `config/etf_context_universe.json`

## Universe support rule

The upstream repo should prioritize support for:
- core broad-market ETFs
- sector ETFs
- high-liquidity large-cap stocks
- thematic / cross-asset proxies such as BTC-related ETFs

## Holdings/context metadata rule

ETF holdings and related mapping artifacts are context metadata rather than minute-level market tape.
They belong under `context/`, not under `data/`.
