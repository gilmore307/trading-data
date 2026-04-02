# trading-data docs

This docs tree is the canonical home for the `trading-data` repository documentation.

`trading-data` is the upstream market-data repository for the trading system.
It owns market-data acquisition, source adapters, raw partitioning, sustainable data-boundary design, and canonical dataset contracts consumed downstream by `trading-model`.

## Read in order

1. `01-overview.md`
2. `02-repo-structure.md`
3. `03-data-and-artifacts.md`
4. `12-regime-clustering-inputs.md`
5. `13-current-input-coverage.md`
6. `14-data-source-boundary-and-model-scope.md`
7. `16-cross-market-overlap-and-session-models.md`
8. `17-future-research-universe-selection.md`

## Core operating model

- `trading-data` is the canonical upstream data layer
- Alpaca is the primary long-term source and current architectural main focus for the future stock-first main line
- Alpaca cross-market overlap data should define the canonical main input layer
- OKX and Bitget should now be treated as supplemental / backup sources rather than the primary architectural center
- crypto-specific enrichments may remain as supplemental data branches
- downstream repositories should consume stable data contracts rather than embed acquisition logic
