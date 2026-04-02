# Time Series Partition Policy

_Last updated: 2026-03-31_

## Goal

Keep all time-series data aligned across datasets while preventing single-file growth from becoming unmanageable for GitHub, dashboard loading, and incremental updates.

Business timezone for partition boundaries: `America/New_York`.

## Core rule

All time-series datasets should share the same partition boundaries.

- Use the highest-density / fastest-growing time-series dataset as the partitioning benchmark.
- Default partition boundary: **business-calendar month in `America/New_York`**.
- All aligned time-series layers should follow the same monthly cut points.

## Default partition unit

Preferred default:
- one file per month
- named as `YYYY-MM.jsonl`

Examples:
- `2024-01.jsonl`
- `2024-02.jsonl`
- `2024-03.jsonl`

## Canonical GitHub-friendly file rule

Every canonical partition file should be small enough to live in GitHub as an ordinary tracked file.

Target size per file:
- ideal: **20 MB – 30 MB**
- acceptable: **10 MB – 30 MB**
- hard warning threshold: **50 MB**

If a monthly file still exceeds the threshold, it must be further subdivided inside the month.
A too-large monthly monolith may exist temporarily as a build convenience, but it is not a canonical storage artifact.

## Time-zone rule

All partition boundaries should use the project business timezone: **America/New_York**.
Do not mix local-time partitions with different business-boundary rules.

## Open vs sealed partitions

- historical months should be treated as sealed/immutable partitions
- the current month may remain an open partition and be rewritten during ongoing ingestion
- once the month closes, it becomes sealed

## Datasets that should follow this rule first

Highest priority:
- raw candles
- market-state dataset
- unsupervised labels

Next priority:
- family equity curves
- composite curves / dashboard-facing time-series outputs

## Datasets that may need additional partition dimensions

Some very large research tables may require more than time-only partitioning.
Examples:
- parameter utility datasets

For those datasets, time should still remain one partition axis, but family / parameter-region / cluster may also be used as additional partition dimensions.

## Why this rule exists

This policy is intended to improve:
- alignment across datasets
- incremental updates
- GitHub friendliness
- on-demand loading for dashboard/server
- future archival / cleanup discipline

## Migration direction

During migration, temporary large monoliths may still exist.
The target direction is:
- canonical time-series datasets live in aligned monthly partitions
- monolithic whole-history files are transitional or build-time convenience artifacts, not the long-term target format
