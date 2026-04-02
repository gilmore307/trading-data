# 02 Repo Structure

This document defines the target repository structure for `trading-data`.

## Target layout

- `docs/` — ordered project/data-contract documentation
- `src/` — source adapters, fetch/update/build code, and data-maintenance logic
- `config/` — source and pipeline configuration
- `data/` — tracked monthly-partitioned market-data storage
- `tests/` — adapter/data-contract tests as the repo matures

## Data layout

The intended data layout should use:
- `data/<symbol>/<YYMM>/<dataset>.jsonl` for tracked symbol/month datasets
- `data/intermediate/` — larger normalized working datasets
- `data/derived/` — compact durable derived outputs
- `data/reports/` — human-facing data-quality or coverage outputs
- `data/manifests/` — inventories, schema notes, retention/control metadata
- `data/docs/` — data-structure notes that belong with the data tree

## Code grouping rule

Source-specific logic should live under `src/`.

Initial expected families:
- `src/data/alpaca/` as the primary source family
- `src/data/okx/` as supplemental/backup source family
- `src/data/bitget/` as supplemental/backup source family
- `src/data/common/` for shared helpers and update/backfill orchestration code

## Scope rule

This repo owns:
- market-data acquisition
- source normalization
- raw partitioning rules
- sustainable canonical input contracts
- optional enrichment-data branches

This repo does not own:
- strategy-family research
- composite logic
- selection/ranking logic
- live runtime execution
