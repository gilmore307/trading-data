# trading-data

Canonical upstream market-data repository for the trading system.

This repository is responsible for:
- market-data acquisition
- source adapters and fetch scripts
- raw data partitioning and storage policy
- cross-market canonical data layers
- sustainable data-boundary definitions
- producing the dataset foundations consumed downstream by `trading-model`

Downstream relationship:
- `trading-data` -> `trading-model` -> `quantitative-trading`

## Documentation

Start with:
- `docs/README.md`
- `docs/01-overview.md`
- `docs/02-repo-structure.md`
- `docs/13-current-input-coverage.md`
- `docs/14-data-source-boundary-and-model-scope.md`

## Current direction

- Alpaca is the primary long-term paid source for the future stock-focused main line
- cross-market overlap data should define the canonical main model input layer
- crypto-specific enrichments may remain as optional supplemental inputs
- this repo should become the canonical home for market-data adapters and data contracts
