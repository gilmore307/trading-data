# feature_01_market_regime

Deterministic generator for the Layer 1 MarketRegimeModel V1 feature table.

## Boundary

- Input: cleaned `source_01_market_regime` bar rows plus reviewed shared CSVs:
  - `market_regime_etf_universe.csv`
  - `market_regime_relative_strength_combinations.csv`
- Output: in-memory feature rows for the single `feature_01_market_regime` table. SQL storage keeps one row per `snapshot_time` and stores generated feature values in `feature_payload_json` JSONB to avoid PostgreSQL row-size limits. Sector/industry rotation, daily-context pair features, sector-observation breadth/dispersion aggregates, and raw ratio moving-average level keys are excluded; rotation evidence belongs to `feature_02_security_selection`, while normalized ratio distance/slope/spread/alignment features remain in Layer 1 when the pair is broad market/cross-asset evidence.
- No provider calls.
- Runtime SQL writes are isolated in `sql.py`; `scripts/generate_feature_01_market_regime.py` is a compatibility wrapper and unit tests do not touch a durable database.
- No generated artifacts committed to Git.

## Key file

- `generator.py` owns feature generation, point-in-time filtering, and feature row output used by the SQL runner and tests.
- `sql.py` owns SQL reads/writes for `trading_data.source_01_market_regime -> trading_data.feature_01_market_regime`.
