# trading-data docs

This docs tree is the canonical home for the `trading-data` repository documentation.

`trading-data` is the canonical upstream market-data repository for the trading system.
It acquires and normalizes market/context data, stores canonical monthly partitions, and exposes stable fetch/build entrypoints that `trading-manager` can call.
It does not own cross-repo orchestration policy.

## Read in workflow order

1. `01-overview.md`
2. `02-storage-contracts-and-partitions.md`
3. `03-context-layer-and-holdings.md`
4. `04-refresh-entrypoints-and-signals.md`
5. `05-current-status-and-open-decisions.md`
6. `06-macro-data.md`

## Appendix

- `appendix-output-compaction-audit-2026-04-03.md`
