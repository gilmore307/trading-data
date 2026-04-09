# 04 Refresh Entrypoints and Signals

This document defines the stable refresh/build entrypoints that `trading-manager` may call and the signal semantics produced by `trading-data`.

## Guiding split

There are two refresh rhythms and they stay separate:
1. market-tape refresh for Alpaca market data
2. permanent-context refresh for macro/economic datasets and other non-market-tape context data

## 1. Alpaca market-data refresh entrypoints

### Current-month refresh entrypoint
Runner family:
- `src/data/alpaca/update_current_month.py`

Behavior:
- refresh the current open month for configured symbols
- maintain resumable canonical month outputs under `trading-storage/2_market_tape/.../<symbol>/<YYMM>/`

### Previous-month batch entrypoint
Runner:
- `src/data/alpaca/update_previous_month_batch.py`

Behavior:
- build/refresh the previous month for the configured batch of symbols
- write retained month outputs under `trading-storage/2_market_tape/.../<symbol>/<YYMM>/`
- emit a downstream-ready signal file under `trading-storage/1_market_regime/0_permanent/8_signals/`

Current signal meaning:
- `market_data_ready`

## 2. Macro / permanent-context refresh entrypoints

Runner families:
- `src/data/macro/fetch_fred_series.py`
- `src/data/macro/fetch_bls_series.py`
- `src/data/macro/fetch_bea_series.py`
- `src/data/macro/fetch_census_series.py`
- `src/data/macro/fetch_treasury_dataset.py`

Behavior:
- fetch or update durable macro/economic context series or datasets
- upsert into canonical permanent context files under `trading-storage/1_market_regime/0_permanent/1_macro/`

Interpretation rule:
- these are context refreshes, not market-tape partitions
- success should mean the target series/dataset file was refreshed successfully

## Signal and state philosophy

Signals should describe artifact readiness, not workflow orchestration state.

Current rule:
- signals should remain machine-readable and scoped to the artifact family they prove ready
- downstream systems may use signals as evidence, but `trading-data` should not try to encode the manager control-plane state machine inside those files

## Current stable manager-facing entrypoints

### Alpaca previous-month market-data batch
- command: `python3 src/data/alpaca/update_previous_month_batch.py [--target-month YYYY-MM] [--batch ...]`
- output class: retained month market-tape partitions in `trading-storage/2_market_tape/`
- downstream signal: `market_data_ready`

### Macro/economic series refresh commands
Examples:
- `python3 src/data/macro/fetch_fred_series.py --series DGS10`
- `python3 src/data/macro/fetch_bls_series.py --series ... --start-year ... --end-year ...`
- `python3 src/data/macro/fetch_bea_series.py --dataset ... --table-name ... --line-number ... --frequency ... --year ...`
- `python3 src/data/macro/fetch_census_series.py --name ... --url ... --fields ... --time-field ...`
- `python3 src/data/macro/fetch_treasury_dataset.py --name ... --endpoint ...`

These should be treated as permanent-context refresh entrypoints rather than market-month builders.
