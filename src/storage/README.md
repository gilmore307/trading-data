# storage

Reusable storage adapters for accepted durable outputs.

Boundary:

- `storage.*` owns low-level persistence adapters and receipt-safe storage metadata.
- Data sources own the semantic table contract they write: table name, columns, natural key, and row normalization.
- Real durable SQL targets are configured by `storage_target` entries and runtime secret aliases; bundle code must not hard-code local database files as canonical outputs.
- Tests may inject fake writers. Local SQLite is not the accepted contract for production model-input outputs.

Current adapters:

- `sql.py` — PostgreSQL table writer for SQL-only bundle outputs.
