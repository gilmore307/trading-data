# ETF holdings context

This directory stores ETF holdings and related normalized mapping artifacts.

## Directory rule

Monthly ETF holdings outputs should be grouped by month directory:
- `context/etf_holdings/<YYMM>/`

Inside each month directory, use one file per ETF:
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

Examples:
- `context/etf_holdings/2603/QQQ_2603.md`
- `context/etf_holdings/2603/IVV_2603.md`
- `context/etf_holdings/2603/SPY_2603.md`

## Intended contents

This layer is intended for:
- ETF -> monthly holdings snapshots
- later reverse mappings such as stock -> candidate ETFs
- candidate context discovery inputs for downstream relevance modeling
- local N-PORT availability/capture state tracking via `_nport_state.json`
- N-PORT discovery/package metadata such as `_nport_discovery.json` and `_nport_packages/`

## Naming split

Keep operational/state helper files at the root of `context/etf_holdings/` only when they are not themselves monthly ETF output artifacts.
Monthly ETF data artifacts should always go into the month subdirectory.

These files are context metadata, not minute-level market tape.
So they belong under `context/`, not under `data/`.
