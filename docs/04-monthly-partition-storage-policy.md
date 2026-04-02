# 04 Monthly Partition Storage Policy

This document records the core storage rule for `trading-data`.

## Core rule

Market data should be stored in this repository and partitioned by month.

That means:
- each dataset is split into monthly files
- current month is append/update friendly
- closed historical months are treated as stable partitions
- partition sizing should remain small enough to keep repository storage and GitHub operations manageable

## Why monthly partitioning is required

Monthly partitioning gives the project:
- bounded file sizes
- easier incremental updates
- clearer backfill/retry behavior
- safer Git tracking for data that still needs to live in the repo
- easier sparse/materialization management later if needed

## Update rule

The intended operating rule is:
- historical data is written month by month
- the current month can be refreshed or appended repeatedly
- new update jobs should target the relevant monthly file rather than rewriting large monolithic datasets

## Path rule

Canonical raw datasets should continue to follow the short project-oriented path rule:
- `data/raw/<symbol>/<dataset>/<YYYY-MM>.jsonl`

Examples:
- `data/raw/BTC-USDT-SWAP/candles/2026-04.jsonl`
- `data/raw/BTCUSDT/funding/2026-04.jsonl`
- `data/raw/BTCUSDT/basis_proxy/2026-04.jsonl`

## Repository rule

For now, the data should live directly in `trading-data`.
This repo is intended to be the canonical tracked home for monthly-partitioned upstream market data and related manifests/contracts.
