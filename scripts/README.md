# scripts

Executable maintenance and operational entrypoints for `trading-data`.

## Files

- `generate_feature_01_market_regime.py` — compatibility wrapper for the Layer 1 feature SQL runner. The importable implementation lives in `src/data_feature/feature_01_market_regime/sql.py` so installed CLI entrypoints and direct script execution share one code path.
- `generate_feature_02_security_selection.py` — compatibility wrapper for the Layer 2 sector/industry rotation feature SQL runner. The importable implementation lives in `src/data_feature/feature_02_security_selection/sql.py`.

## Boundary

Scripts may import reusable code from `src/`. Reusable pipeline/generator logic belongs in `src/`, not here.
