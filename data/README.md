# data

This directory stores tracked market-tape datasets only.

## Canonical path rule

Use:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

Examples:
- `data/AAPL/2604/bars_1min.jsonl`
- `data/AAPL/2604/quotes.jsonl`
- `data/AAPL/2604/trades.jsonl`
- `data/BTC-USD/2604/bars_1min.jsonl`

## Layering rule

`data/` should contain only real market datasets.
Do not store ETF holdings, mapping artifacts, state files, or other non-market-tape context metadata here.
Those belong under `context/`.

## Data-layer structure

Current canonical layers:
- `raw` — source-native or near-source-native captured datasets
- `intermediate` — reusable transformed datasets that are still upstream/data-layer artifacts
- `derived` — durable derived outputs generated from upstream datasets
- `reports` — human-readable summaries, diagnostics, or generated review artifacts
- `manifests` — machine-readable inventory / freshness / coverage metadata

For the current first-wave repo state, the primary tracked raw market-tape layout is:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

If additional layer directories are introduced later, keep their meaning explicit and do not mix them into the symbol/month market-tape tree.

## Partition rule

- partition by symbol first
- partition by business-month directory using `YYMM`
- keep one dataset per file within the month directory
- treat minute-level bars as the canonical raw bar layer

## Current canonical datasets

Mainline overlap datasets:
- `bars_1min.jsonl`
- `quotes.jsonl`
- `trades.jsonl`

Context datasets currently still stored under symbol/month market-tape path when sourced from Alpaca:
- `news.jsonl`
- `options_snapshots.jsonl`

Row/meta storage note:
- each `data/<symbol>/<YYMM>/` directory now uses a shared `_meta.json`
- row JSONL files keep only changing row fields
- `_meta.json` stores shared month-level dataset metadata needed for clean logical reconstruction
- supported compact datasets now include:
  - `bars_1min.jsonl`
  - `quotes.jsonl`
  - `trades.jsonl`
  - `options_snapshots.jsonl`
- the supported reader path is `src/data/common/read_market_tape_rows.py`
- important logical fields such as dataset identity, symbol identity, options underlying identity, and feed context remain recoverable through the reader path

## Resume / append expectation

Fetchers should be written so repeated runs can safely resume without corrupting monthly partitions or creating uncontrolled duplication.
