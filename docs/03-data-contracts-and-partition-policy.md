# 03 Data Contracts and Partition Policy

This document defines the main data contract, source-priority rules, partition policy, dedupe policy, and compact-row storage rules for `trading-data`.

## Source priority

### Primary source
Alpaca is the primary long-term source and current architectural main focus.

Reason:
- future main battlefield is stocks
- Alpaca supports stocks, ETFs, options context, news, and crypto overlap data
- Alpaca provides the cross-market overlap surface that should define the canonical mainline input layer

### Supplemental / backup sources
#### OKX
Use as:
- supplemental crypto source
- backup candles source
- reference source when needed

#### Bitget
Use as:
- supplemental crypto enrichment source
- backup/reference source
- provider of optional derivatives-specific context when useful

## Canonical-vs-supplemental rule

- Alpaca-supported cross-market overlap data should shape the canonical contract
- OKX/Bitget data should not redefine the mainline architecture unless there is a specific reason and a stock-portable equivalent story
- crypto-only enrichments remain optional/supplemental

## Canonical raw granularity rule

The canonical raw market-data layer should be minute-level across all supported asset classes.

That means:
- minute-level bars are the canonical raw bar layer
- higher timeframes are derived/aggregated layers

Main raw bar object:
- `bars_1min.jsonl`

## Canonical overlap surface

The canonical mainline input surface should be defined by data that Alpaca supports across both stocks and crypto.

Directly verified common categories include:
- historical bars
- historical quotes
- historical trades
- latest bars
- latest quotes
- latest trades
- snapshots

## Canonical derived features

The canonical mainline feature families should primarily derive from the overlap surface, such as:
- returns
- volatility
- range/structure
- volume
- trade count
- VWAP-relative structure
- quote spread / mid / quote-derived imbalance proxies
- trade activity intensity
- session / calendar context

## Optional enrichment contract

Data families without strong stock-portable equivalents remain optional/supplemental, such as:
- funding
- basis/premium
- crypto-specific OI semantics
- liquidation feeds
- crypto-specific orderbook enrichments

## Time-series partition policy

All time-series datasets should share the same partition boundaries where alignment matters.

Core rules:
- use business-calendar month boundaries in `America/New_York`
- historical months should be treated as sealed/immutable partitions
- the current month may remain open and be rewritten during ingestion
- canonical tracked partition files should remain GitHub-friendly in size

Current mainline market-tape path rule:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

## Canonical dedupe rule

Repeated runs must be resumable without unbounded output growth.

Current canonical dedupe rules:
- `bars_1min.jsonl`: one row per `(symbol, ts)`
- `quotes.jsonl`: one row per `(symbol, ts)`
- `trades.jsonl`: one row per `(symbol, ts)`
- `news.jsonl`: one row per `id`
- `options_snapshots.jsonl`: one row per `(option_symbol, ts)` within a month partition

For `options_snapshots.jsonl`, if multiple rows collide on `(option_symbol, ts)`, keep the best available canonical row rather than appending all variants forever.

## Row/meta split rule for compact monthly storage

Some month files now use a compact row/meta split when repeated month-level constants would otherwise be written on every row.

Practical rule:
- prefer storage reduction only when it does not noticeably hurt direct usability
- important logical fields such as dataset identity, symbol identity, options-underlying identity, asset class, feed scope, and timeframe should still be recoverable cleanly through the supported reader path

Current adopted files/pattern:
- `data/<symbol>/<YYMM>/_meta.json`
- `data/<symbol>/<YYMM>/options_snapshots.jsonl`
- `data/<symbol>/<YYMM>/bars_1min.jsonl`
- `data/<symbol>/<YYMM>/quotes.jsonl`
- `data/<symbol>/<YYMM>/trades.jsonl`

The shared month-directory `_meta.json` carries repeated metadata needed for compact storage and clean reconstruction.
Each compact JSONL row keeps only the changing fields for that dataset.

Logical consumers should treat the row file plus the directory `_meta.json` as one dataset surface.
The supported compatibility reader is:
- `src/data/common/read_market_tape_rows.py`

## Current compact writer/reader contract

Current Alpaca writers that follow the compact month-directory contract:
- `src/data/alpaca/fetch_option_snapshots.py`
- `src/data/alpaca/fetch_historical_bars.py`
- `src/data/alpaca/fetch_historical_quotes.py`
- `src/data/alpaca/fetch_historical_trades.py`

Shared metadata helpers:
- `src/data/common/month_meta_utils.py`

## Important note on audits and migration utilities

Detailed storage-change rationale and savings analysis belong in appendices/audit notes, not in the main workflow docs.
The operational contract for downstream readers is simply:
- use the canonical path
- respect business-month partitioning
- reconstruct logical rows through the supported reader path when `_meta.json` is present
