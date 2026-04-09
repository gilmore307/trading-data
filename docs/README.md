# trading-data docs

This docs tree is the canonical documentation layer for `trading-data`.

Use it in this order:
1. `01-overview.md` — repository role, boundaries, and stack position
2. `02-storage-contracts-and-partitions.md` — canonical retained-artifact and path contract
3. `03-context-layer-and-holdings.md` — context/ETF/macro placement rules
4. `04-refresh-entrypoints-and-signals.md` — manager-facing runnable entrypoints and signal semantics
5. `05-current-status-and-open-decisions.md` — what is implemented vs still unsettled
6. `06-macro-data.md` — permanent market-regime macro/calendar layer
7. `07-market-regime-benchmarks.md` — retained benchmark/proxy universe and intended use

## Reading rule
- `README.md` = fast operator entrypoint
- `docs/` = durable design and contract layer
- `TODO.md` = next queued work

## Current integration rule
`trading-data` is code-first, but its durable outputs should land in `trading-storage` by default.
