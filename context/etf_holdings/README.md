# ETF holdings context

This directory stores ETF holdings outputs and related N-PORT helper artifacts.

## Base-layer output rule

This directory stores the maintained ETF holdings base snapshots.

Monthly ETF holdings outputs should be grouped by month directory:
- `context/etf_holdings/<YYMM>/`

Inside each month directory, use one file per ETF:
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

Examples:
- `context/etf_holdings/2603/QQQ_2603.md`
- `context/etf_holdings/2603/IVV_2603.md`
- `context/etf_holdings/2603/SPY_2603.md`

These month-partitioned ETF files are the ETF holdings base layer used to derive per-symbol downstream context later.
The ready-to-use downstream per-symbol artifact should instead live under:
- `context/constituent_etf_deltas/<SYMBOL>.md`

That per-symbol file should append monthly ETF membership/weight records only.
It should not precompute month-over-month delta logic in this repo.

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
