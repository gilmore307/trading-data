# Output Compaction Audit — 2026-04-03

## Goal

Reduce tracked output size without harming data completeness or making downstream consumption more awkward.

## What was audited

All tracked `data/**/*.jsonl` files in the current `trading-data` repo snapshot.

## Result summary

Initial audit result before rewrite:
- files scanned: 26
- changed files if compacted: 3
- total rows before: 2337
- total rows after: 2285
- removed rows: 52
- estimated bytes before: 911396
- estimated bytes after: 872455
- estimated bytes saved: 38941

Actual in-place compaction applied:
- `data/AAPL/2602/options_snapshots.jsonl`
- `data/AAPL/2603/options_snapshots.jsonl`
- `data/AAPL/2604/options_snapshots.jsonl`

Per-file savings:
- `data/AAPL/2602/options_snapshots.jsonl`: 2 -> 1 rows, saved 648 bytes
- `data/AAPL/2603/options_snapshots.jsonl`: 60 -> 32 rows, saved 20680 bytes
- `data/AAPL/2604/options_snapshots.jsonl`: 140 -> 117 rows, saved 17559 bytes

## Main finding

The current material output bloat is concentrated in `options_snapshots.jsonl`, not in the other tracked monthly datasets.

Observed pattern:
- same `(option_symbol, ts)` written multiple times
- later rows often differ only in `snapshot.latestQuote.*`
- bars / quotes / trades / news did not show the same collision pattern in the audited files

Root cause:
- `src/data/alpaca/fetch_option_snapshots.py` had been append-only
- other main Alpaca fetchers already used read-existing -> key-overwrite -> rewrite-month behavior

## Adopted rule

`options_snapshots.jsonl` now uses one canonical row per `(option_symbol, ts)` within a month partition.

When duplicates collide, keep the best row by this preference order:
1. richer populated snapshot sub-objects
2. more informative non-blank `latestQuote.c`
3. later `latestQuote.t`

This is intended as a pragmatic storage/control rule for the current repo contract, not a claim that later quote refreshes are globally unimportant.
If we later need full intra-key version history, that should become a distinct event-log style dataset rather than uncontrolled duplication inside the canonical monthly partition.

## Current recommendation for other output files

Do **not** aggressively field-trim or restructure other mainline files yet.

Current view:
- `bars_1min.jsonl`: already canonical and compact enough for current readability needs
- `quotes.jsonl`: no duplicate-write inflation detected in the current tracked sample
- `trades.jsonl`: no duplicate-write inflation detected in the current tracked sample
- `news.jsonl`: deduped by article id already; no meaningful bloat pattern found

So the next storage-efficiency gains, if needed, are more likely to come from:
- retention policy
- alternate packed/derived storage layers
- manifest-backed compression formats for low-change context datasets

—not from blindly removing fields from the current canonical JSONL contracts.

## Tooling added

- `src/data/common/audit_output_compaction.py`

Example usage:
- audit only: `python3 src/data/common/audit_output_compaction.py`
- apply supported compaction in place: `python3 src/data/common/audit_output_compaction.py --apply`

## Follow-up question

The only open contract question left from this pass:
- should options snapshots remain a single canonical row per `(option_symbol, ts)`
- or should we later split them into a compact canonical snapshot file plus an explicit optional revision/event-log file for quote refresh history

For now, the canonical-row approach is the best fit for storage pressure + convenience.
