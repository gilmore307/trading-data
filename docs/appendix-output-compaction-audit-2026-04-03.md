# Output Compaction Audit — 2026-04-03

## Goal

Reduce tracked output size without harming data completeness or making downstream consumption more awkward.

## Final storage direction adopted

The repo now uses a compact month-directory metadata model for the main redundant market-tape outputs.

Current compact pattern:
- `data/<symbol>/<YYMM>/_meta.json`
- `data/<symbol>/<YYMM>/bars_1min.jsonl`
- `data/<symbol>/<YYMM>/quotes.jsonl`
- `data/<symbol>/<YYMM>/trades.jsonl`
- `data/<symbol>/<YYMM>/options_snapshots.jsonl`

Important constraint:
- storage reduction should not noticeably harm direct usability
- important logical fields such as dataset identity, symbol identity, options-underlying identity, asset class, feed scope, and timeframe must remain cleanly recoverable through the supported reader path

Supported reader path:
- `src/data/common/read_market_tape_rows.py`

Shared metadata helpers:
- `src/data/common/month_meta_utils.py`

## Phase 1 — duplicate-write cleanup

All tracked `data/**/*.jsonl` files in the initial repo snapshot were audited for duplicate-write inflation.

Result before rewrite:
- files scanned: 26
- changed files if compacted: 3
- total rows before: 2337
- total rows after: 2285
- removed rows: 52
- estimated bytes before: 911396
- estimated bytes after: 872455
- estimated bytes saved: 38941

Actual duplicate cleanup applied:
- `data/AAPL/2602/options_snapshots.jsonl`
- `data/AAPL/2603/options_snapshots.jsonl`
- `data/AAPL/2604/options_snapshots.jsonl`

Per-file savings from duplicate cleanup:
- `data/AAPL/2602/options_snapshots.jsonl`: 2 -> 1 rows, saved 648 bytes
- `data/AAPL/2603/options_snapshots.jsonl`: 60 -> 32 rows, saved 20680 bytes
- `data/AAPL/2604/options_snapshots.jsonl`: 140 -> 117 rows, saved 17559 bytes

Main finding from phase 1:
- the material duplicate-write bloat was concentrated in `options_snapshots.jsonl`
- bars / quotes / trades / news did not show the same collision pattern in the audited files

Root cause from phase 1:
- `src/data/alpaca/fetch_option_snapshots.py` had been append-only
- other main Alpaca fetchers already used read-existing -> key-overwrite -> rewrite-month behavior

## Phase 2 — row/meta split and metadata centralization

The user's primary storage concern was not only duplicate rows, but also repeated month-level constants inside every row such as:
- `source: alpaca`
- `dataset: ...`
- `symbol` / `underlying_symbol`
- `asset_class`
- `feed_scope`
- `timeframe`

Applied storage changes in this pass:
1. `options_snapshots.jsonl` moved to compact row storage
2. `bars_1min.jsonl`, `quotes.jsonl`, and `trades.jsonl` also moved to compact row storage where profitable
3. per-dataset sidecar meta files were then consolidated into one month-directory `_meta.json`
4. `_meta.json` was then further minified so path-derivable or over-verbose metadata does not dominate the savings
5. fetchers were updated so future writes follow the same compact contract rather than recreating old per-dataset sidecar meta files

## Realized savings in this pass

### Duplicate cleanup
- 38941 bytes saved

### Options row/meta split
- 26326 bytes saved

### Bars / quotes / trades row/meta split
- 212473 bytes saved

### Directory `_meta.json` minification
- 6756 bytes saved

## Combined gross savings

Total gross savings realized across the completed pass:
- **284496 bytes**
- approximately **277.8 KB**

## Current dataset status

### Fully handled in this pass
- `options_snapshots.jsonl`
- `bars_1min.jsonl`
- `quotes.jsonl`
- `trades.jsonl`

These now participate in the compact row + month-directory `_meta.json` contract.

### Evaluated but not yet converted
- `news.jsonl`

Current `news.jsonl` estimate from the tracked sample:
- `AAPL/2603/news.jsonl`: save ~82 bytes
- `AAPL/2604/news.jsonl`: save ~681 bytes
- `QQQ/2604/news.jsonl`: save ~490 bytes
- `SPY/2604/news.jsonl`: save ~1929 bytes

Interpretation:
- `news.jsonl` does have some repeated constants (`source`, `dataset`, `source_name`)
- but the current savings are relatively small compared with the mainline market-tape datasets
- the conversion is not yet blocked, just lower priority

## Current reader / writer contract

### Writers
Current Alpaca writers now write toward the compact month-directory meta contract:
- `src/data/alpaca/fetch_option_snapshots.py`
- `src/data/alpaca/fetch_historical_bars.py`
- `src/data/alpaca/fetch_historical_quotes.py`
- `src/data/alpaca/fetch_historical_trades.py`

### Readers
Use:
- `src/data/common/read_market_tape_rows.py`

This reader reconstructs important logical fields such as:
- `source`
- `dataset`
- `symbol`
- `underlying_symbol`
- `asset_class`
- `feed_scope`
- `timeframe`
- `month`

## Tooling added/kept

- `src/data/common/audit_output_compaction.py`
- `src/data/common/month_meta_utils.py`
- `src/data/common/read_market_tape_rows.py`
- `src/data/common/normalize_options_snapshot_storage.py`
- `src/data/common/normalize_market_tape_row_meta.py`
- `src/data/common/normalize_directory_meta.py`
- `src/data/common/minify_directory_meta.py`

Some of these are migration utilities from this compaction pass rather than long-term runtime-critical entrypoints.

## Remaining follow-up items

Open design questions left after the completed pass:
- should options snapshots remain a single canonical row per `(option_symbol, ts)` or evolve into a more explicitly versioned/event-log contract later
- should `news.jsonl` also adopt the compact row + `_meta.json` pattern when month files grow larger
- if `news.jsonl` is compacted later, should `source_name` remain row-level or move into metadata when constant inside a month file

## Bottom line

The output-compaction pass is now complete for the main redundant market-tape files.

The repo has moved from:
- repeated full logical metadata on every row
- plus duplicated options snapshot writes

to:
- canonical deduped options snapshots
- compact row storage for the mainline market-tape files
- one shared `_meta.json` per symbol/month directory
- one supported logical-reader path for downstream reconstruction
