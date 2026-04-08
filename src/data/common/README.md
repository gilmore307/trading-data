# common data utilities

Shared helpers and maintenance utilities for `trading-data` source families.

Use this directory for:
- common partition helpers
- shared source-agnostic data utilities
- storage/data-contract maintenance helpers
- compatibility readers and compaction/normalization helpers

Do not use this directory as a hidden workflow-orchestration layer.
If something is primarily about scheduling, queueing, retry policy, cross-repo sequencing, cleanup eligibility, or archive/rehydration control-plane policy, it belongs in `trading-manager`.

Do not keep SEC/N-PORT-specific ETF holdings workflows here anymore.
Those now belong under `src/data/nport/`.

Keep source-specific logic inside the matching source family whenever possible.
