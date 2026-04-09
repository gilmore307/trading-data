# 30 Entrypoints and Signals

This document defines the stable manager-facing execution surfaces exposed by `trading-data`.

## Two refresh classes
1. market-tape refresh
2. permanent-context refresh

## Market-tape entrypoints

### Current-month maintenance
Runner family:
- `src/data/alpaca/update_current_month.py`

Behavior:
- refresh the current open month for configured symbols
- maintain resumable canonical month outputs under `trading-storage/2_market_tape/.../<symbol>/<YYMM>/`

### Previous-month batch
Runner:
- `src/data/alpaca/update_previous_month_batch.py`

Behavior:
- build/refresh the previous month for the configured batch of symbols
- write retained month outputs under `trading-storage/2_market_tape/.../<symbol>/<YYMM>/`
- emit a downstream-ready signal file under `trading-storage/1_market_regime/0_permanent/8_signals/`

Current signal meaning:
- `market_data_ready`

## Permanent-context entrypoints
Runner families:
- `src/data/macro/fetch_fred_series.py`
- `src/data/macro/fetch_bls_series.py`
- `src/data/macro/fetch_bea_series.py`
- `src/data/macro/fetch_census_series.py`
- `src/data/macro/fetch_treasury_dataset.py`
- calendar builders under `src/data/macro/`

Behavior:
- fetch or update durable macro/economic context series, datasets, or calendars
- upsert into canonical permanent files under `trading-storage/1_market_regime/0_permanent/`

## Signal philosophy
Signals should describe artifact readiness, not manager control-plane state.

Current rule:
- signals remain machine-readable and artifact-scoped
- manager may use them as evidence
- `trading-data` should not encode queue/workflow state machines inside the signal payload
