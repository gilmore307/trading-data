# 02 Repo Structure

This document defines the target repository structure for `trading-data`.

## Target layout

- `docs/` — ordered Markdown documentation and data-boundary references
- `src/` — fetch/update/build entrypoints for source adapters and data maintenance
- `config/` — source and pipeline configuration
- `data/` — canonical market-data repository tree
- `tests/` — adapter/data-contract tests as the repo matures

## Canonical data layout

The intended data layout should follow these top-level layers:
- `data/raw/` — raw factual source datasets
- `data/intermediate/` — large working datasets / normalization outputs
- `data/derived/` — compact derived outputs suitable for normal repo workflows
- `data/reports/` — human-facing report artifacts related to the data layer
- `data/manifests/` — inventories, indexes, schema notes, retention metadata
- `data/docs/` — data-structure/policy notes that belong with the data repo

## Source-adapter grouping rule

Source-specific acquisition logic should live under `src/` in a way that keeps adapter ownership clear.

Initial expected families include:
- Alpaca adapters as the primary source family
- OKX adapters as supplemental/backup source family
- Bitget adapters as supplemental/backup source family
- update/backfill orchestration code

## Scope rule

This repo should own:
- market-data acquisition
- raw partitioning rules
- source normalization
- sustainable canonical input contracts
- optional enrichment-data boundaries

This repo should not own:
- strategy family research
- composite construction logic
- ranking/selection logic
- live runtime execution

## Practical interpretation

When adding new work:
- data acquisition / normalization code belongs here
- source/data policy docs belong here
- canonical data contracts belong here
- downstream repos should consume stable data outputs rather than embedding their own acquisition logic
