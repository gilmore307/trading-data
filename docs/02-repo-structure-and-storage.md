# 02 Repo Structure and Storage

This document defines the repository structure and canonical storage layout for `trading-data`.

## Target layout

- `docs/` — ordered project/data-contract documentation
- `src/` — source adapters, fetch/update/build code, and data-maintenance logic
- `config/` — source and pipeline configuration
- `data/` — tracked monthly-partitioned market-tape storage
- `context/` — non-market-tape context metadata such as ETF holdings and mapping artifacts
- `tests/` — adapter/data-contract tests as the repo matures

## Scope rule

This repo owns:
- market-data acquisition
- source normalization
- raw partitioning rules
- sustainable canonical input contracts
- optional enrichment-data branches

This repo does not own:
- strategy-family research
- composite logic
- selection/ranking logic
- live runtime execution

## Data layout

The tracked `data/` tree should stay simple and contain only real symbol/month market dataset files:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

Do not keep empty placeholder subtrees under `data/` just to reserve future concepts.
If future non-tape metadata is needed, place it under `context/` or another deliberate location instead of leaving unused empty directories inside the main data tree.

## Canonical market-tape storage

Canonical market-tape path:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

Examples:
- `data/AAPL/2604/bars_1min.jsonl`
- `data/BTC-USD/2603/bars_1min.jsonl`
- `data/AAPL/2604/quotes.jsonl`
- `data/AAPL/2604/trades.jsonl`

Symbol-format note:
- Alpaca crypto API requests use slash form such as `BTC/USD`
- on-disk path normalization should still use a safe symbol directory such as `BTC-USD`

Keep `data/` focused on actual market dataset files only.

## Canonical data layers

Repository-level data-layer meanings are:
- `raw` — source-native or near-source-native captured datasets
- `intermediate` — reusable transformed datasets that are still part of the upstream data layer
- `derived` — durable derived outputs generated from upstream datasets
- `reports` — human-readable diagnostics, audits, or review artifacts
- `manifests` — machine-readable coverage / freshness / inventory metadata

Current first-wave tracked mainline storage remains the direct symbol/month path:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

## Compact month-directory metadata pattern

For datasets that carry heavy month-level repeated constants, a month-directory shared meta file is allowed when it materially reduces duplicated row payload without hurting usability.

Current adopted pattern:
- `data/<symbol>/<YYMM>/_meta.json`
- `data/<symbol>/<YYMM>/bars_1min.jsonl`
- `data/<symbol>/<YYMM>/quotes.jsonl`
- `data/<symbol>/<YYMM>/trades.jsonl`
- `data/<symbol>/<YYMM>/options_snapshots.jsonl`

The directory `_meta.json` is the canonical metadata companion for compact month files in that directory.

## Context-layer storage rule

ETF holdings and related mapping artifacts are context metadata rather than minute-level market tape.
They belong under `context/`, not under `data/`.

Current important context paths include:
- `context/etf_holdings/`
- `context/constituent_etf_deltas/`
- `context/signals/`

## Code grouping rule

Source-specific logic should live under `src/`.

Current expected families:
- `src/data/alpaca/` as the primary source family
- `src/data/okx/` as supplemental/backup source family
- `src/data/bitget/` as supplemental/backup source family
- `src/data/nport/` for ETF holdings/N-PORT workflows
- `src/data/common/` for shared helpers and maintenance/orchestration code
