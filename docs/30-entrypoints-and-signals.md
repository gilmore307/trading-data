# 30 Entrypoints and Signals

This document defines the stable manager-facing execution surfaces exposed by `trading-data`.

## Two refresh classes
1. market-tape refresh
2. market-regime/context refresh

## Market-tape entrypoints

### Current-month maintenance
Runner family:
- `src/data/alpaca/update_current_month.py`

Behavior:
- refresh the current open month for configured symbols
- maintain resumable canonical month outputs under `trading-storage/2_market_tape/1_data/.../<symbol>/<YYMM>/`

### Previous-month batch
Runner:
- `src/data/alpaca/update_previous_month_batch.py`

Behavior:
- build/refresh the previous month for the configured batch of symbols
- write retained month outputs under `trading-storage/2_market_tape/1_data/.../<symbol>/<YYMM>/`
- emit a downstream-ready signal file under `trading-storage/2_market_tape/3_credentials/1_bars/<symbol>/`

Current signal meaning:
- `market_data_ready`
- the single-symbol monthly Alpaca entrypoint must always emit a completion signal instead of finishing without readiness evidence, because manager-ledger advancement depends on that artifact

## Market-regime/context entrypoints
Runner families:
- `src/data/macro/fetch_fred_series.py`
- `src/data/macro/fetch_bls_series.py`
- `src/data/macro/fetch_bea_series.py`
- `src/data/macro/fetch_census_series.py`
- `src/data/macro/fetch_treasury_dataset.py`
- calendar builders under `src/data/macro/`
- regime ETF/proxy Alpaca refresh entrypoints

Behavior:
- fetch or update durable market-regime context series, datasets, calendars, or ETF/proxy bars
- upsert into canonical files under `trading-storage/1_market_regime/1_data/`
- emit regime readiness signals under `trading-storage/1_market_regime/3_credentials/...`

## Signal philosophy
Signals should describe artifact readiness, not manager control-plane state.

Current rule:
- signals remain machine-readable and artifact-scoped
- manager may use them as evidence
- `trading-data` should not encode queue/workflow state machines inside the signal payload
- stdout/stderr and other execution traces belong in storage temporary partitions, not in signal files
- each domain should keep its own signal tree under `3_credentials/`, structurally aligned with `1_data/`

## Existing-artifact restart rule
If a rerun encounters an already-existing target file:
- do not mark it complete only because it exists
- classify it as `missing`, `ready`, `partial`, or `invalid`
- treat `invalid` as delete-and-rebuild
