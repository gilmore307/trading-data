# storage

Low-level persistence helpers live here.

Boundary:

- `storage.*` provides adapters and receipt-safe metadata helpers.
- Data sources own semantic table contracts: table name, columns, keys, timestamps, and row normalization.
- Durable targets are configured through reviewed storage/request contracts and secret aliases; local files or test databases are not production contracts.
- Tests may inject fake writers. Local SQLite-style fixtures are development evidence only.

Current adapters:

- `sql.py` — PostgreSQL writer for accepted SQL source/feature outputs.
