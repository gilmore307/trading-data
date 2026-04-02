# trading-data

Canonical upstream market-data repository for the trading system.

This repository is responsible for:
- market-data acquisition
- source adapters and data-maintenance code under `src/`
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

- Alpaca is the primary long-term source and current main focus for the future stock-focused main line
- Alpaca cross-market overlap data should define the canonical main model input layer
- OKX and Bitget should now be treated as supplemental / backup data sources rather than the primary architectural center
- crypto-specific enrichments may remain as optional supplemental inputs
- this repo should become the canonical home for market-data adapters and data contracts
