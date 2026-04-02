# ETF holdings context

This directory stores ETF holdings outputs and related N-PORT helper artifacts.

## Primary output rule

The primary downstream-facing output of this directory is the monthly ETF -> constituent mapping result.

Monthly ETF holdings outputs should be grouped by month directory:
- `context/etf_holdings/<YYMM>/`

Inside each month directory, use one file per ETF:
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

Examples:
- `context/etf_holdings/2603/QQQ_2603.md`
- `context/etf_holdings/2603/IVV_2603.md`
- `context/etf_holdings/2603/SPY_2603.md`

These month-partitioned ETF files are the artifacts intended to be passed downstream to `trading-model`.

## Auxiliary files

All non-primary helper artifacts should stay under:
- `context/etf_holdings/_aux/`

Current auxiliary split:
- `_aux/mapping/` — intermediate ETF -> SEC series candidate matches
- `_aux/state/` — retry/progress state such as N-PORT availability/capture state
- `_aux/discovery/` — discovered quarterly package metadata/index files
- `_aux/nport_data/` — downloaded N-PORT package metadata/readme/materials
- `_aux/samples/` — development-only sample inputs

## Data semantics

This layer is intended for:
- ETF -> monthly holdings snapshots
- later reverse mappings such as stock -> candidate ETFs
- candidate context discovery inputs for downstream relevance modeling

These files are context metadata, not minute-level market tape.
So they belong under `context/`, not under `data/`.
