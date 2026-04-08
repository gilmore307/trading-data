# 05 Current Status and Open Decisions

This document captures the current implemented state of `trading-data`, plus the main open decisions still worth tracking.

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
- first-wave macro/economic fetchers now exist for:
  - FRED
  - BLS
  - BEA
  - Census
  - Treasury Fiscal Data
- Federal Reserve official event sources remain planned rather than fully implemented

## Still incomplete / not yet hardened
- broader operational hardening and validation for macro source families
- release-calendar handling for official macro sources
- clearer source-specific freshness/index visibility for permanent context data
- final storage boundary cleanup between `trading-data` and `trading-storage`
- concrete manager-side execution against the new regime release-task ledger

## Current contract clarifications
- `quotes_1min.jsonl` and `trades_1min.jsonl` are minute-level aggregates, not persisted raw event-tape files
- per-dataset state files such as `quotes_1min.state.json` and `trades_1min.state.json` describe resumable partition completion state, not process liveness
- `complete=false` means non-final/open/interrupted resumable state; it does not by itself mean a builder is still running

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
- how aggressively official macro release calendars should be normalized into local machine-readable policy/config
- how much repo-local artifact state should remain versus move entirely into `trading-storage`
- whether any additional large low-change datasets should adopt the compact row/meta pattern later

## Notable recent decisions
- 2026-04-03: compact row/meta split was adopted as a mainline retained market-tape contract for the supported month datasets
- 2026-04-07: a new storage-only sibling project `projects/trading-storage` was introduced so the trading code repos can stay code-first while shared downloaded/context/intermediate/report/output artifacts converge into one storage-first location
- 2026-04-08: first-wave official-source fetchers for FRED / BLS / BEA / Census / Treasury are now present in `src/data/macro/`, so the main remaining work is release-calendar handling, registry cleanup, and operational hardening rather than initial adapter creation
- 2026-04-08: ETF constituent look-through was removed from the active mainline design so ETFs remain bar/context proxies for regime and divergence analysis
- 2026-04-08: regime-side calendar refresh was folded into the unified `release_dataset_refresh_tasks.csv` design, with `plan_at` introduced as the earliest eligible execution timestamp for scheduled or immediate tasks
