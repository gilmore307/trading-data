# storage/

`storage/` is the local storage boundary for `trading-data`.

## Tracked content

- `templates/` — committed storage-facing templates and generated final data-kind preview files.

## Ignored local content

Task outputs, probe reports, receipts, logs, raw provider evidence, cleaned run-local data, and other generated artifacts are local-only and ignored by Git unless a future durable storage contract explicitly promotes them.

During development, bundle defaults write task outputs under `storage/<task-id>/`. Durable SQL output contracts remain future `trading-storage` work.
