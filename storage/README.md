# storage/

`storage/` is the ignored local development storage boundary for `trading-data`.

Task outputs, probe reports, receipts, logs, raw provider evidence, cleaned run-local data, and other generated artifacts are local-only and ignored by Git unless a future durable storage contract explicitly promotes them.

Accepted model-input outputs now use reviewed SQL storage definitions in `src/trading_data/storage/sql.py` and bundle README contracts. The former committed `storage/templates/data_kinds/` preview catalog has been retired.
