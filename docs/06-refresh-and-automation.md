# 06 Refresh and Automation

This document defines how `trading-data` should refresh automatically going forward.

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

### Output rule
This runner should:
- backfill the previous month only
- write into the normal symbol/month market-tape partitions under `data/`
- preserve canonical per-dataset dedupe rules when rerun against existing month files
- emit a downstream-ready signal file under `context/signals/` when a batch finishes

Current downstream signal meaning:
- `market_data_ready`

## 2. ETF holdings / N-PORT monthly retry strategy

### Rule
ETF holdings should be updated once per month for the **previous month**.
Because the exact SEC/N-PORT publication date is uncertain, the system should try once per day until the target month becomes available and is captured.

Current runner:
- `src/data/nport/update_previous_month_etf_holdings.py`

Supporting helpers live under:
- `src/data/nport/`

### Target-universe rule
Do not attempt the full ETF universe by default.
Use the actionable ETF holdings target universe at:
- `config/etf_holdings_target_universe.json`

### Output rule
This runner should:
- attempt discovery/availability for the previous month
- run extraction only when the target month appears available
- continue automatically into ETF data decomposition/output build for the configured ETF target list
- generate month directory outputs under `context/etf_holdings/<YYMM>/`
- update N-PORT state under the holdings context area
- emit a downstream-ready signal file under `context/signals/` after successful capture

Current downstream signal meaning:
- `etf_holdings_ready`

## 3. Downstream signal rule

`trading-data` should emit durable machine-readable signals when refresh work completes.
Signals belong under:
- `context/signals/`

These signals are for downstream consumers such as `trading-model`.
They indicate that data refresh has completed and downstream validation/model work may begin.

## 4. Future scheduler rule

These runners are designed to be called by system tasks later.
The scheduler should eventually control:
- monthly Alpaca backfill tasks
- daily N-PORT retry tasks

The scheduler layer should remain separate from the repo business logic.
The repo should provide stable entrypoints; system tasks should call those entrypoints.
