# 02 Storage Contracts and Partitions

This document defines the repository structure, canonical storage layout, source-priority rules, partition policy, and compact-row storage contract for `trading-data`.

## Target layout
- `docs/` — ordered data-contract documentation
- `src/` — source adapters, fetch/update/build code, and maintenance logic
- `config/` — source and pipeline configuration that belongs to the data layer
- `data/` — tracked monthly-partitioned market-tape storage
- `context/` — non-market-tape context metadata such as ETF holdings, macro/economic series, event calendars, and mapping artifacts
- `tests/` — adapter/data-contract tests as the repo matures

## Scope rule

This repo owns:
- market-data acquisition
- source normalization
- raw partitioning rules
- sustainable canonical input contracts
- optional enrichment-data branches
- runnable fetch/build entrypoints that can be called by `trading-manager`

This repo does not own:
- strategy-family research
- composite logic
- selection/ranking logic
- live runtime execution
- workflow sequencing ownership
- scheduler/control-plane state
- cross-repo archive/rehydration policy

## Source priority

### Primary source
Alpaca is the primary long-term source and current architectural main focus.

### Supplemental / backup sources
- OKX as supplemental crypto source / backup candles path
- Bitget as supplemental enrichment / backup/reference path

## Canonical-vs-supplemental rule
- Alpaca-supported cross-market overlap data shapes the canonical contract
- OKX/Bitget do not redefine the mainline architecture unless a specific reason exists
- crypto-only enrichments remain optional/supplemental

## Low-frequency / context storage rule

Macro/economic series, ETF holdings context, and similar context datasets should not be forced into market-tape-style symbol/month partitions.

Current rule:
- use `context/` rather than `data/` for these artifacts
- prefer append/upsert accumulation within the context layer rather than treating them as market-tape partitions
- for single-series or single-dataset official sources, prefer one durable file per logical series or dataset
- for N-PORT ETF -> constituent holdings, prefer permanent month-directory accumulation under the context layer because the natural retained object is a month snapshot set rather than a symbol/month tape partition
- for constituent -> ETF derived context, prefer symbol-facing context artifacts under `context/` that can be refreshed with the underlying symbol's usable context state
- prefer full-history backfill first, then periodic append/update

Examples:
- `context/macro/fred/DGS10.jsonl`
- `context/macro/fred/CPIAUCSL.jsonl`
- `context/macro/bls/CUUR0000SA0.jsonl`
- `context/macro/bea/GDPC1.jsonl`
- `context/macro/census/retail_sales.jsonl`
- `context/macro/treasury/debt_to_penny.jsonl`
- `context/macro/events/fomc_calendar.jsonl`
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

## Canonical market-tape storage

Mainline path rule:
- use canonical month files under `data/<symbol>/<YYMM>/`
- current retained market-tape datasets are minute-level files rather than raw quote/trade event partitions
- resumable builders may also maintain sidecar state files during open/incomplete runs

Examples:
- `data/AAPL/2604/bars_1min.jsonl`
- `data/AAPL/2604/quotes_1min.jsonl`
- `data/AAPL/2604/trades_1min.jsonl`
- `data/AAPL/2604/options_snapshots.jsonl`
- `data/AAPL/2604/_meta.json`
- `data/AAPL/2604/quotes_1min.state.json`
- `data/AAPL/2604/trades_1min.state.json`

## Canonical retained granularity rule

The canonical retained market-data layer is minute-level across supported asset classes.
Current retained market-tape objects:
- `bars_1min.jsonl`
- `quotes_1min.jsonl`
- `trades_1min.jsonl`

Terminology rule:
- `quotes_1min.jsonl` and `trades_1min.jsonl` are minute-level aggregates derived from raw quote/trade events during ingestion
- they are not the same thing as a persisted raw event tape

## Time-series partition policy

All time-series datasets should share alignment boundaries where that matters.

Core rules:
- use business-calendar month boundaries in `America/New_York`
- target-month fetch windows must also be defined in `America/New_York`, then converted to UTC only for API transport
- do not define month windows in UTC and then infer business-month partitioning afterward
- unless an external API/transport contract explicitly requires UTC, internal trading-stack time semantics should default to America/New_York
- historical months are sealed/immutable partitions
- the current month may remain open and be rewritten during ingestion
- canonical tracked partition files should remain GitHub-friendly in size

## Canonical dedupe rule

Repeated runs must be resumable without unbounded output growth.

Current canonical rules:
- `bars_1min.jsonl`: one row per `(symbol, ts)`
- `quotes_1min.jsonl`: one row per `(symbol, minute)` aggregated from raw quote events during ingestion
- `trades_1min.jsonl`: one row per `(symbol, minute)` aggregated from raw trade events during ingestion
- `news.jsonl`: one row per `id`
- `options_snapshots.jsonl`: one row per `(option_symbol, ts)` within a month partition

## Compact row/meta split rule

Some month files use a compact row/meta split when repeated month-level constants would otherwise be written on every row.
This is now part of the mainline retained market-tape contract rather than an appendix-only optimization note.

Current adopted pattern:
- `data/<symbol>/<YYMM>/_meta.json`
- `data/<symbol>/<YYMM>/bars_1min.jsonl`
- `data/<symbol>/<YYMM>/quotes_1min.jsonl`
- `data/<symbol>/<YYMM>/trades_1min.jsonl`
- `data/<symbol>/<YYMM>/options_snapshots.jsonl`

Current compaction conclusions folded into the mainline contract:
- the most material duplicate-write bloat was concentrated in `options_snapshots.jsonl`
- the repo now uses one shared month-directory `_meta.json` rather than per-dataset duplicated sidecar metadata
- `bars_1min`, `quotes_1min`, `trades_1min`, and `options_snapshots` now participate in the compact row + shared month-meta pattern
- `news.jsonl` remains outside that compact contract for now because the observed savings were much smaller in the audited sample

Aggregation rule:
- raw quote and raw trade events should be aggregated to minute level during ingestion rather than persisted as the default long-term canonical store
- the default canonical layer should align to the minute-level market-tape boundary used by `bars_1min`
- canonical `timestamp` fields should be stored in `America/New_York` local time with offset; UTC human-readable timestamp fields should not be retained in the default canonical layer
- optional raw event capture, if ever reintroduced, should be explicitly opt-in rather than the default mainline storage contract

Current aggregate semantics:
- `quotes_1min.jsonl` = one row per `(symbol, minute)` with quote-derived minute aggregates such as bid/ask/mid/spread OHLC-style fields, quote counts, and size summaries
- `trades_1min.jsonl` = one row per `(symbol, minute)` with trade-derived minute aggregates such as price OHLC, trade counts, volume, notional, and VWAP

The supported compatibility reader is:
- `src/data/common/read_market_tape_rows.py`

## Code grouping rule

Current expected families:
- `src/data/alpaca/`
- `src/data/okx/`
- `src/data/bitget/`
- `src/data/nport/`
- `src/data/common/`

`src/data/common/` should not become a hidden orchestration layer.
If behavior is mainly about cross-repo workflow timing, queueing, retries, cleanup eligibility, or archive policy, it belongs in `trading-manager`.
