# 04 Monthly Partition Storage Policy

This document records the core storage rule for `trading-data`.

## Core rule

Market data should be stored in this repository and partitioned by symbol and month.

That means:
- each symbol gets its own directory under `data/`
- each month gets its own subdirectory under that symbol
- named dataset files live inside the month directory
- current month is append/update friendly
- closed historical months are treated as stable partitions
- partition sizing should remain small enough to keep repository storage and GitHub operations manageable

## Canonical raw granularity rule

The canonical raw market-data layer should be minute-level across all supported asset classes.

That means:
- minute-level bars are the canonical raw bar layer
- higher timeframes should be treated as derived/aggregated layers
- downstream modeling should assume minute-level canonical raw inputs by default

## Why monthly partitioning is required

Monthly partitioning gives the project:
- bounded file sizes
- easier incremental updates
- clearer backfill/retry behavior
- safer Git tracking for data that still needs to live in the repo
- easier sparse/materialization management later if needed

## Update rule

The intended operating rule is:
- historical data is written symbol by symbol, month by month
- the current month directory can be refreshed or appended repeatedly
- new update jobs should target the relevant symbol/month dataset file rather than rewriting large monolithic datasets

## Path rule

Canonical tracked datasets should follow the symbol/month directory rule:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

Examples:
- `data/BTC-USD/2603/bars_1Hour.jsonl`
- `data/AAPL/2603/bars_1Day.jsonl`
- `data/BTCUSDT/2604/funding.jsonl`
- `data/BTCUSDT/2604/basis_proxy.jsonl`

## Repository rule

For now, the data should live directly in `trading-data`.
This repo is intended to be the canonical tracked home for monthly-partitioned upstream market data.

Practical rule:
- keep `data/` focused on actual dataset files
- do not leave unused placeholder folders under `data/`
- if non-dataset artifacts are needed later, place them intentionally rather than pre-creating empty structure
