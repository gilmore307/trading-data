# trading-data

`trading-data` is the canonical upstream market-data repository for the trading stack.
It acquires and normalizes market/context data, stores canonical monthly partitions, and exposes stable refresh/build entrypoints that `trading-manager` can call.

## Scope

**Owns**
- market-data acquisition
- source adapters and data-maintenance code
- raw partitioning and storage policy
- canonical data-layer contracts
- ETF/context-layer artifacts
- stable data refresh/build entrypoints
- readiness signals for completed artifacts

**Does not own**
- cross-repo scheduling/timing policy
- queue/control-plane state
- strategy simulation
- model training/ranking logic
- live execution
- cross-repo archive/rehydration policy ownership

## Stack position

```mermaid
flowchart LR
    TD[trading-data] --> TS[trading-strategy]
    TD --> TM[trading-model]
    MG[trading-manager] -.orchestrates.-> TD
```

## Required inputs
- external API/source responses from Alpaca
- repo config under `config/*.json`
- source credentials via repo-local environment

## Optional inputs
- OKX API responses
- Bitget API responses
- SEC / N-PORT discovery pages and source files
- low-frequency macro/economic source responses from FRED, BLS, BEA, Census, and Treasury Fiscal Data
- Federal Reserve official webpage/RSS/calendar event sources
- local helper/state files under `context/etf_holdings/_aux/`

## Primary outputs
- `data/<symbol>/<YYMM>/bars_1min.jsonl`
- `data/<symbol>/<YYMM>/quotes_1min.jsonl`
- `data/<symbol>/<YYMM>/trades_1min.jsonl`
- `data/<symbol>/<YYMM>/news.jsonl` when present
- `data/<symbol>/<YYMM>/options_snapshots.jsonl` when present
- `data/<symbol>/<YYMM>/_meta.json`
- `context/macro/fred/<series>.jsonl`
- `context/macro/bls/<series>.jsonl`
- `context/macro/bea/<series>.jsonl`
- `context/macro/census/<series>.jsonl`
- `context/macro/treasury/<dataset>.jsonl`
- `context/macro/events/*.jsonl`
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`
- `context/constituent_etf_deltas/<SYMBOL>.md`

## Completion artifacts
- `context/signals/*.json`
  - `market_data_ready...json`
  - `etf_holdings_ready...json`

## Data flow

```mermaid
flowchart TD
    A[Source adapters] --> B[Monthly partitions under data/]
    A --> C[Context artifacts under context/]
    B --> D[Ready signals]
    C --> D
    D --> E[trading-manager / downstream consumers]
```

## Current mainline direction

- Alpaca is the primary long-term source and current architectural mainline
- OKX and Bitget are supplemental / backup sources
- monthly market-tape partitions are the canonical retained market input layer
- the retained market-tape contract is minute-level by default:
  - `bars_1min.jsonl`
  - `quotes_1min.jsonl`
  - `trades_1min.jsonl`
- `quotes_1min.jsonl` and `trades_1min.jsonl` are minute aggregates, not raw event-tape persistence
- low-frequency macro/economic data should be treated as context artifacts rather than symbol/month tape
- macro/economic series should prefer full-history append/upsert storage per series rather than market-tape-style month partitioning
- N-PORT ETF holdings should also be treated as context artifacts with permanent append/upsert month accumulation under the context layer rather than as market-tape partitions
- ETF holdings and related mappings live in the context layer
- downstream artifact readiness is signaled through machine-readable signal files

## Documentation

Read in order:
1. `docs/README.md`
2. `docs/01-overview.md`
3. `docs/02-storage-contracts-and-partitions.md`
4. `docs/03-context-layer-and-holdings.md`
5. `docs/04-refresh-entrypoints-and-signals.md`
6. `docs/05-current-status-and-open-decisions.md`
7. `docs/06-macro-data.md`
8. `docs/07-market-regime-benchmarks.md`
