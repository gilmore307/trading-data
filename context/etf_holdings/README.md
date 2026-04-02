# ETF holdings context

This directory stores ETF holdings and related normalized mapping artifacts.

This layer is intended for:
- ETF -> holdings snapshots
- later reverse mappings such as stock -> candidate ETFs
- candidate context discovery inputs for downstream relevance modeling
- local N-PORT availability/capture state tracking via `_nport_state.json`
- N-PORT discovery/package metadata such as `_nport_discovery.json` and `_nport_packages/`
- normalized per-ETF holdings files such as `SPY.json`

These files are context metadata, not minute-level market tape.
So they belong under `context/`, not under `data/`.
