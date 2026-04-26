# data/storage/

Development-stage local file output root for `trading-data` task runs.

Purpose:

- keep development data out of SQL databases;
- make generated outputs easy to inspect and delete;
- avoid polluting durable storage while schemas and contracts are still changing.

Rules:

- Do not commit generated files from this directory.
- Store only local development artifacts, temporary task outputs, and development completion receipts here.
- Treat contents as disposable unless explicitly copied into an accepted storage contract later.
- Keep raw provider responses, cleaned outputs, manifests, and receipts separated by task/run when implementation begins.

Registered config:

- `TRADING_DATA_DEVELOPMENT_STORAGE_ROOT`
- relative path: `data/storage`
- local path: `/root/projects/trading-data/data/storage`

Production or durable storage remains future `trading-storage` contract work.
