# trading-data docs

This docs tree is the canonical home for the `trading-data` repository documentation.

`trading-data` is the upstream market-data repository for the trading system.
It owns source adapters, acquisition/update workflows, monthly-partitioned data storage, minute-level canonical raw data rules, sustainable data-boundary design, and canonical data contracts consumed downstream.

## Read in workflow order

1. `01-overview.md`
2. `02-repo-structure-and-storage.md`
3. `03-data-contracts-and-partition-policy.md`
4. `04-context-and-holdings-layer.md`
5. `05-source-coverage-and-operational-status.md`
6. `06-refresh-and-automation.md`

## Appendix / audit docs

- `appendix-output-compaction-audit-2026-04-03.md`

## Notes

- main workflow docs should describe the stable contract and operating model
- one-off audits, migration notes, or implementation forensics should live as appendices rather than mixed into the main ordered path
