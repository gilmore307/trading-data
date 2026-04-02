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
- current-month refresh/update orchestration for one or more approved symbols

Key entrypoints:
- `fetch_historical_bars.py`
- `fetch_historical_quotes.py`
- `fetch_historical_trades.py`
- `fetch_news.py`
- `fetch_option_snapshots.py`
- `update_current_month.py`
- `update_previous_month_batch.py`

Batch update note:
- `update_current_month.py` supports either a single `--symbol` / `--asset-class` pair or a JSON symbol universe file via `--symbols-file`
- current repo default universe config: `config/alpaca_symbol_universe.json`
- fetchers also auto-read repo-local credentials from `projects/trading-data/.env` when present
- batch refresh now automatically limits `news` and `options` collection to stock symbols so crypto runs do not emit avoidable non-applicable failures
- `update_previous_month_batch.py` is the intended stable entrypoint for future monthly system-task backfills of the previous completed month

This adapter family should define the mainline upstream contract surface wherever possible.
