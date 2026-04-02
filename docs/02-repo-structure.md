# 02 Repo Structure

This document defines the target repository structure for `trading-data`.

## Target layout

- `docs/` — ordered project/data-contract documentation
- `src/` — source adapters, fetch/update/build code, and data-maintenance logic
- `config/` — source and pipeline configuration
- `data/` — tracked monthly-partitioned market-tape storage
- `context/` — non-market-tape context metadata such as ETF holdings and mapping artifacts
- `tests/` — adapter/data-contract tests as the repo matures

## Data layout

The tracked `data/` tree should stay simple and contain only real symbol/month market dataset files:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

Do not keep empty placeholder subtrees under `data/` just to reserve future concepts.
If future non-tape metadata is needed, place it under `context/` or another deliberate location instead of leaving unused empty directories inside the main data tree.

## Canonical data layers

The repository-level data layer meanings are:
- `raw` — source-native or near-source-native captured datasets
- `intermediate` — reusable transformed datasets that are still part of the upstream data layer
- `derived` — durable derived outputs generated from upstream datasets
- `reports` — human-readable diagnostics, audits, or review artifacts
- `manifests` — machine-readable coverage / freshness / inventory metadata

Current first-wave tracked mainline storage remains the direct symbol/month raw path:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

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
