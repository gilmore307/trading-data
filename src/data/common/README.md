# common data utilities

Shared helpers and maintenance entrypoints for `trading-data` source families.

Use this directory for:
- shared update orchestration
- common partition helpers
- shared source-agnostic data utilities
- SEC/N-PORT discovery and normalization helpers that are not tied to one market-data source family
- future stable system-task entrypoints for low-frequency context refresh workflows

Keep source-specific logic inside the matching source family whenever possible.
