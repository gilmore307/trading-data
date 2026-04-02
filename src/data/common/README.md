# common data utilities

Shared helpers and maintenance entrypoints for `trading-data` source families.

Use this directory for:
- shared update orchestration
- common partition helpers
- shared source-agnostic data utilities
- future stable system-task entrypoints for low-frequency context refresh workflows

Do not keep SEC/N-PORT-specific ETF holdings workflows here anymore.
Those now belong under `src/data/nport/`.

Keep source-specific logic inside the matching source family whenever possible.
