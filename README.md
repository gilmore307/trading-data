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
- `trading-data` -> `trading-model` -> `quantitative-trading`

## Documentation

Start with:
- `docs/README.md`
- `docs/01-overview.md`
- `docs/02-repo-structure.md`
- `docs/03-data-policy-and-contracts.md`
- `docs/04-context-and-universe.md`
- `docs/05-holdings-source-and-refresh.md`
- `docs/06-source-coverage-and-status.md`

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
