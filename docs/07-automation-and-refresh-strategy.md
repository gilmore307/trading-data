# 07 Automation and Refresh Strategy

This document defines how `trading-data` should update automatically going forward.

## Guiding split

There are two different refresh rhythms and they should stay separate:

1. market-tape refresh for Alpaca market data
2. low-frequency ETF holdings refresh for N-PORT context data

Do not force both onto the same cadence.

## 1. Alpaca monthly market-data backfill

### Rule

Alpaca market data should be refreshed once per month for the **previous completed month**.

Example:
- if the current month is April, the update target is March market data

### Batch rule

Do not require the entire approved symbol universe to update on the same day.
Split the monthly symbol universe into separate day-batches.

Machine-readable batch config:
- `config/alpaca_monthly_batches.json`

Current runner:
- `src/data/alpaca/update_previous_month_batch.py`

Example usage:
- `python3 src/data/alpaca/update_previous_month_batch.py --batch day_01`
- `python3 src/data/alpaca/update_previous_month_batch.py --batch day_02`

### Output rule

This runner should:
- backfill the previous month only
- write into the normal symbol/month market-tape partitions under `data/`
- emit a downstream-ready signal file under `context/signals/` when a batch finishes

Current downstream signal meaning:
- `market_data_ready`
- tells downstream model-building layers that the finished batch is ready for data validation and testing

## 2. ETF holdings / N-PORT monthly retry strategy

### Rule

ETF holdings should be updated once per month for the **previous month**.
Because the exact SEC/N-PORT publication date is uncertain, the system should try once per day until the target month becomes available and is captured.

Example:
- if the current month is April, the holdings target month is March
- run one attempt per day
- if not yet published, stop and retry the next day
- once captured, stop retrying for that target month

Current runner:
- `src/data/common/update_previous_month_etf_holdings.py`

Supporting helpers:
- `check_nport_availability.py`
- `discover_nport_dataset.py`
- `download_nport_metadata.py`
- `map_etf_to_sec_series.py`
- `extract_series_holdings_from_nport.py`
- `update_etf_holdings_from_nport.py`

### Target-universe rule

Do not attempt the full ETF universe by default.
Use the actionable ETF holdings target universe at:
- `config/etf_holdings_target_universe.json`

### Output rule

This runner should:
- attempt discovery/availability for the previous month
- run extraction only when the target month appears available
- update `context/etf_holdings/_nport_state.json`
- emit a downstream-ready signal file under `context/signals/` after successful capture

Current downstream signal meaning:
- `etf_holdings_ready`
- tells downstream model-building layers that context/holdings validation and testing can begin

## 3. Downstream signal rule

`trading-data` should emit durable machine-readable signals when refresh work completes.
Signals belong under:
- `context/signals/`

These signals are for downstream consumers such as `trading-model`.
They should not submit work directly themselves, but they should clearly indicate that data refresh has completed and model/data tests may begin.

## 4. Future scheduler rule

These runners are designed to be called by system tasks later.
The scheduler should eventually control:

### Monthly Alpaca backfill tasks
- one task per day-batch near the start of each month

### Daily N-PORT retry task
- one daily attempt for the previous month until capture succeeds

The scheduler layer should remain separate from the repo business logic.
The repo should provide stable entrypoints; system tasks should call those entrypoints.
