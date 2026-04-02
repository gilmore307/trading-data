# ETF holdings context

This directory stores ETF holdings and related normalized mapping artifacts.

This layer is intended for:
- ETF -> holdings snapshots
- later reverse mappings such as stock -> candidate ETFs
- candidate context discovery inputs for downstream relevance modeling

These files are context metadata, not minute-level market tape.
So they belong under `context/`, not under `data/`.
