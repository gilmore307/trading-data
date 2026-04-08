# 05 Current Status and Open Decisions

This document summarizes current source coverage, operational status, and the remaining open contract decisions.

## Alpaca verified capabilities
- stock historical bars / quotes / trades
- stock latest bars / quotes / trades
- stock snapshots
- stock extended-hours historical bars
- crypto historical bars / quotes / trades
- crypto latest bars / quotes / trades
- crypto snapshots
- crypto latest orderbooks
- news
- options snapshots
- options contract metadata including open interest
- options latest quote / trade
- paper/account access

## Supplemental-source verified capabilities
- OKX historical candles fetch
- Bitget funding fetch
- Bitget mark/index fetch
- Bitget basis-proxy build

## Operational now
- Alpaca market-tape overlap path
- Alpaca news path
- Alpaca options-context path
- current-month Alpaca refresh via repo runners
- previous-month Alpaca batch backfill via stable repo entrypoint
- retained minute-level market-tape outputs:
  - `bars_1min.jsonl`
  - `quotes_1min.jsonl`
  - `trades_1min.jsonl`
- OKX supplemental candles path
- Bitget supplemental enrichment path
- N-PORT discovery/extraction/build scaffold for ETF holdings context
- first-wave macro/economic fetchers now exist for:
  - FRED
  - BLS
  - BEA
  - Census
  - Treasury Fiscal Data
- Federal Reserve official event sources remain planned rather than fully implemented

## Current rebuild status
- 2026-04-07: experimental downloaded data under `data/` and `context/` was intentionally cleared so the repo can be rebuilt from a clean empty-state database baseline
- 2026-04-07: first clean rebuild attempt exposed a runner bug in `src/data/alpaca/update_previous_month_batch.py` where child Python processes did not inherit a repo-root `PYTHONPATH`, causing `ModuleNotFoundError: No module named 'src'`
- 2026-04-07: the batch runner was patched to inject the repo root into child-process `PYTHONPATH` so manager-style subprocess execution works from a clean environment
- 2026-04-07: a new storage-only sibling project `projects/trading-storage` was introduced so the trading code repos can stay code-first while shared downloaded/context/intermediate/report/output artifacts converge into one storage-first location
- 2026-04-08: first-wave official-source fetchers for FRED / BLS / BEA / Census / Treasury are now present in `src/data/macro/`, so the main remaining work is source/dataset registry cleanup, release-calendar handling, Fed event sources, and operational hardening rather than initial adapter creation

## Candidate but not fully operational now
- `etf.com` candidate ETF discovery path
- `etfdb.com` candidate ETF discovery path
- Finnhub ETF holdings path
- SEC/N-PORT holdings path is promising but not yet a fully hardened production path

## Current contract clarifications
- `quotes_1min.jsonl` and `trades_1min.jsonl` are minute-level aggregates, not persisted raw event-tape files
- per-dataset state files such as `quotes_1min.state.json` and `trades_1min.state.json` describe resumable partition completion state, not process liveness
- `complete=false` means non-final/open/interrupted resumable state; it does not by itself mean a builder is still running
- N-PORT ETF holdings should be interpreted as permanent context accumulation under `context/etf_holdings/`, not as market-tape partitions under `data/`

## Output compaction contract now belongs to the mainline docs

The prior standalone compaction appendix has been folded into the mainline contract:
- the canonical retained market-tape month directory uses one shared `_meta.json`
- the mainline compact month-directory contract covers:
  - `bars_1min.jsonl`
  - `quotes_1min.jsonl`
  - `trades_1min.jsonl`
  - `options_snapshots.jsonl`
- the main material duplicate-write bloat that motivated compaction was concentrated in `options_snapshots.jsonl`
- `news.jsonl` remains unconverted for now because the observed savings were much smaller in the audited sample

Current compact-contract interpretation:
- repeated month-level constants should live in `_meta.json` when that materially reduces tracked storage without hurting logical usability
- the supported downstream reconstruction path is `src/data/common/read_market_tape_rows.py`
- compaction is now part of the main retained market-tape contract rather than a one-off appendix-only decision

## Open decisions
- whether options snapshots should remain a single canonical row per `(option_symbol, ts)` or later evolve into a more explicit versioned/event-log contract
- whether news should stay as-is or later adopt a row/meta split when larger month files accumulate
- if news volume grows materially, whether `source_name` should remain row-level or move into month metadata when constant within a month file

## Appendix / audit note

Detailed storage-change rationale and savings analysis remain in:
- `appendix-output-compaction-audit-2026-04-03.md`
