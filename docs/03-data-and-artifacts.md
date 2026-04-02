# 03 Data and Artifacts

This document summarizes the intended data boundary for `trading-data`.

## Core rule

`trading-data` is responsible for canonical market-data storage structure and data contracts.

## Main repository responsibilities

### `data/raw/`
For:
- raw source data fetched from supported providers
- canonical monthly partitions
- factual upstream records before downstream modeling interpretation

### `data/intermediate/`
For:
- normalized working datasets
- merged source-alignment outputs
- feature-ready but still process-oriented tables

### `data/derived/`
For:
- compact, durable outputs convenient for downstream repos
- stable data products derived from heavier upstream/intermediate work

### `data/reports/`
For:
- human-facing data-quality reports
- adapter/fetch summaries
- data coverage outputs

### `data/manifests/`
For:
- inventories
- schema notes
- retention metadata
- sparse/materialization control metadata

## Canonical-vs-optional rule

This repo should distinguish between:

### canonical data layer
Data that defines the sustainable long-term mainline input surface, especially for future stock-first work.

### optional enrichment layer
Data that may improve research but should not define the only workable model path if it is not portable or sustainable.

## Current strategic implication

At the current planning stage:
- Alpaca-compatible cross-market data should shape the canonical mainline input layer
- crypto-only enrichments should be treated as supplemental, not canonical
