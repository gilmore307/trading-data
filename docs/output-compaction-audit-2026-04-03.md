# Output Compaction Audit — 2026-04-03

## Goal

Reduce tracked output size without harming data completeness or making downstream consumption more awkward.

## Phase 1 — duplicate-write cleanup

All tracked `data/**/*.jsonl` files in the current `trading-data` repo snapshot were audited for duplicate-write inflation.

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

## Phase 2 — row/meta split for repeated row constants

The user’s primary storage concern was not only duplicate rows, but also repeated month-level constants inside every options snapshot row, such as:
- `source: alpaca`
- `dataset: options_snapshot`
- `underlying_symbol: <symbol>`

Adopted storage change:
- row data stays in `data/<symbol>/<YYMM>/options_snapshots.jsonl`
- repeated month-level constants move to `data/<symbol>/<YYMM>/options_snapshots.meta.json`

Current row payload fields:
- `option_symbol`
- `ts`
- `timestamp`
- `snapshot`

Current month-meta fields:
- `source`
- `dataset`
- `underlying_symbol`
- storage format metadata

Compatibility rule:
- logical readers should treat the row file plus sidecar meta file as one dataset
- `src/data/common/read_options_snapshot_rows.py` can reconstruct full logical rows at read time

## Phase 2 result summary

Options snapshot month files normalized: 7

Total options storage before row/meta split:
- 256778 bytes

Total options storage after row/meta split:
- 230605 bytes

Additional bytes saved from row/meta split:
- 26326 bytes

Per-file result:
- `data/AAPL/2602/options_snapshots.jsonl` + meta: 648 -> 801 bytes (tiny-file overhead; no savings)
- `data/AAPL/2603/options_snapshots.*`: 23869 -> 21542 bytes, saved 2327 bytes
- `data/AAPL/2604/options_snapshots.*`: 82529 -> 73402 bytes, saved 9127 bytes
- `data/QQQ/2603/options_snapshots.*`: 8339 -> 7702 bytes, saved 637 bytes
- `data/QQQ/2604/options_snapshots.*`: 67955 -> 61156 bytes, saved 6799 bytes
- `data/SPY/2603/options_snapshots.*`: 10744 -> 9870 bytes, saved 874 bytes
- `data/SPY/2604/options_snapshots.*`: 62694 -> 56132 bytes, saved 6562 bytes

## Combined result from both phases

Combined savings now realized in this pass:
- duplicate cleanup savings: 38941 bytes
- row/meta split savings: 26326 bytes
- combined gross savings: 65267 bytes

## Current recommendation for other output files

Do **not** aggressively field-trim or restructure the other mainline files yet.

Current view:
- `bars_1min.jsonl`: already canonical and reasonably compact for current readability needs
- `quotes.jsonl`: no duplicate-write inflation detected in the current tracked sample
- `trades.jsonl`: no duplicate-write inflation detected in the current tracked sample
- `news.jsonl`: deduped by article id already; no meaningful bloat pattern found

However, some datasets do have obvious repeated month-level constants and may deserve a similar row/meta split later, especially:
- `bars_1min.jsonl`
- `quotes.jsonl`
- `trades.jsonl`

That should be a deliberate second pass after validating the options path first.

## Tooling added

- `src/data/common/audit_output_compaction.py`
- `src/data/common/normalize_options_snapshot_storage.py`
- `src/data/common/read_options_snapshot_rows.py`

Example usage:
- duplicate audit only: `python3 src/data/common/audit_output_compaction.py`
- apply duplicate cleanup: `python3 src/data/common/audit_output_compaction.py --apply`
- preview options row/meta normalization: `python3 src/data/common/normalize_options_snapshot_storage.py`
- apply options row/meta normalization: `python3 src/data/common/normalize_options_snapshot_storage.py --apply`

## Follow-up items

Open contract/design questions left from this pass:
- should options snapshots remain a single canonical row per `(option_symbol, ts)`
- or should they later split into a compact canonical snapshot file plus an explicit optional revision/event-log file for quote refresh history
- should tiny options month files skip sidecar meta to avoid negative savings
- should bars / quotes / trades later adopt the same row/meta split pattern
