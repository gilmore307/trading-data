# scripts

Thin executable wrappers for `trading-data`.

Reusable implementation belongs in `src/`. A script may import `src` code and pass through CLI arguments, but it should not own business logic, contracts, or source-specific behavior.

## Files

- `generate_feature_01_market_regime.py` — wrapper for `data_feature.feature_01_market_regime.sql`.
- `generate_feature_02_sector_context.py` — wrapper for `data_feature.feature_02_sector_context.sql`.

Installed package entrypoints in `pyproject.toml` are the preferred CLI surface for feeds, sources, and features.
