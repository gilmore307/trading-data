# trading-data

Canonical upstream market-data repository for the trading system.

This repository is responsible for:
- market-data acquisition
- source adapters and data-maintenance code under `src/`
- raw data partitioning and storage policy
- cross-market canonical data layers
- sustainable data-boundary definitions
- producing the dataset foundations consumed downstream by `trading-model`

Downstream relationship:
- `trading-data` -> `trading-model` -> `trading-execution`

## Documentation

Start with:
- `docs/README.md`
- `docs/01-overview.md`
- `docs/02-repo-structure-and-storage.md`
- `docs/03-data-contracts-and-partition-policy.md`
- `docs/04-context-and-holdings-layer.md`
- `docs/05-source-coverage-and-operational-status.md`
- `docs/06-refresh-and-automation.md`

## Current direction

- Alpaca is the primary long-term source and current main focus for the future stock-focused main line
- Alpaca cross-market overlap data should define the canonical main model input layer
- OKX and Bitget should now be treated as supplemental / backup data sources rather than the primary architectural center
- crypto-specific enrichments may remain as optional supplemental inputs
- this repo should become the canonical home for market-data adapters and data contracts

## Downstream-facing outputs

The next stage (`trading-model`) should primarily inherit these outputs from `trading-data`:

### 1. Monthly market-tape partitions
Path rule:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

Current canonical datasets include:
- `bars_1min.jsonl`
- `quotes.jsonl`
- `trades.jsonl`
- optional stock context datasets such as `news.jsonl` and `options_snapshots.jsonl`

These files are the primary upstream market-data inputs for downstream validation, feature construction, and model testing.

### 2. ETF monthly holdings base snapshots
Path rule:
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

These are the maintained ETF holdings base snapshots for the target ETF list.
They are upstream context-layer base data, not the main ready-to-use constituent output.

### 3. Ready-to-use per-symbol ETF context files
Path rule:
- `context/constituent_etf_deltas/<SYMBOL>.md`

These are the downstream-facing per-symbol files that accumulate monthly ETF membership/weight context records for the researched symbol.
`trading-data` should append the monthly ETF context data here and leave month-over-month comparison/delta calculation to downstream modeling layers.

### 4. Refresh-completion signals
Path rule:
- `context/signals/*.json`

Current signal families:
- `market_data_ready` — previous-month Alpaca market-data batch finished
- `etf_holdings_ready` — previous-month ETF holdings capture/build finished

These machine-readable signals tell downstream systems when validation and test workflows may begin.

## Auxiliary / non-primary artifacts

The following are helper artifacts and should not be treated as primary downstream data products:
- `context/etf_holdings/_aux/`
- N-PORT discovery/state/package helper files
- intermediate ETF -> SEC series mapping candidates
- month-level coverage manifests

## Research object classes and supported context layers

### 1. Stock research objects
For stock research/trading candidates, `trading-data` may prepare:
- full Alpaca stock market data for the researched symbol
- stock news and options context
- ETF holdings base snapshots
- per-symbol ETF context records under `context/constituent_etf_deltas/<SYMBOL>.md`

In short: stocks may use all relevant Alpaca and N-PORT-derived ETF context layers.

### 2. ETF research objects
For ETF research/trading candidates:
- the ETF itself may use its own Alpaca market/news/options data
- ETF -> ETF context layering should not be treated as the primary self-context path
- non-ETF macro/cross-asset context may still be used where relevant

### 3. Crypto research objects
Crypto trades 24 hours.
That means:
- during stock-market trading hours, crypto research may also use the corresponding ETF and ETF-options context where relevant
- outside stock-market trading hours, crypto research should rely on its own base market data path rather than stock/ETF market context

## Practical handoff rule to `trading-model`

`trading-data` should not try to precompute ready-to-use per-company outputs for the entire US market.
Instead:
- maintain the ETF holdings base layer for the tracked ETF list
- when a specific research symbol is requested, derive and update that symbol's per-symbol ETF context file
- hand the researched symbol's market data plus its ETF context file to `trading-model`
