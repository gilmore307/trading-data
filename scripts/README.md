# scripts

This directory holds market-data acquisition and maintenance entrypoints for `trading-data`.

## Current seeded scripts

Under `scripts/data/`:
- `fetch_okx_history_candles.py`
- `fetch_bitget_derivatives_context.py`
- `update_raw_monthly_data.py`
- `run_btc_only_backfill.sh`
- `run_initial_history_backfill.sh`

## Direction

These scripts were initially seeded from `trading-model` during the repo split.
They should be normalized here over time so `trading-data` becomes the canonical home for source adapters and data-maintenance workflows.
