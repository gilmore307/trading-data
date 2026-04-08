# alpaca adapter family

This directory is the primary source-adapter family for `trading-data`.

Alpaca is the primary long-term source and current main development focus.

Expected responsibilities here:
- stock data acquisition
- ETF/context data acquisition
- crypto overlap data acquisition
- options-context acquisition
- news acquisition
- normalization into canonical minute-level monthly partitions
- stable callable refresh/build entrypoints for approved symbols or configured batches

Key entrypoints:
- `fetch_historical_bars.py`
- `fetch_historical_quotes.py`
- `fetch_historical_trades.py`
- `fetch_news.py`
- `fetch_option_snapshots.py`
- `src/data/common/audit_output_compaction.py` can audit current output files and compact supported datasets such as `options_snapshots.jsonl`
- `src/data/common/normalize_options_snapshot_storage.py` converts options snapshot month files into compact row-data + month-meta storage
- `src/data/common/read_options_snapshot_rows.py` is a compatibility reader that reconstructs full logical rows from the compact storage format
- `update_current_month.py`
- `update_previous_month_batch.py`

Batch update note:
- `update_current_month.py` supports either a single `--symbol` / `--asset-class` pair or a JSON symbol universe file via `--symbols-file`
- current repo default universe config: `config/alpaca_symbol_universe.json`
- fetchers also auto-read repo-local credentials from `projects/trading-data/.env` when present
- batch refresh now automatically limits `news` and `options` collection to stock symbols so crypto runs do not emit avoidable non-applicable failures
- `update_previous_month_batch.py` is the intended stable data-layer entrypoint for manager-triggered monthly backfills of the previous completed month

This adapter family should define the mainline upstream contract surface wherever possible.
