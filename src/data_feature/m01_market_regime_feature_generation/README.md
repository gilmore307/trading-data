# m01_market_regime_feature_generation

Deterministic generator for the Layer 1 MarketRegimeModel market-context feature table.

## Boundary

- Input: cleaned `m01_market_regime_data_acquisition` bar rows plus reviewed shared CSVs:
  - `layer_01_02_market_context_etf_universe.csv`
  - `layer_01_02_market_context_relative_strength_combinations.csv`
- Output: in-memory feature rows for the single `m01_market_regime_feature_generation` table. SQL storage keeps one row per `snapshot_time + input_frame + prediction_horizon + market_universe_ref` and stores generated feature values in `feature_payload_json` JSONB to avoid PostgreSQL row-size limits. The shared CSV `model_layer` column is the authoritative scope discriminator: Layer 1 consumes only `layer_01_market_regime` universe/combination rows. Sector/industry rotation, daily-context pair features, sector-observation breadth/dispersion aggregates, and raw ratio moving-average level keys and standalone SHY return/trend keys are excluded; rotation evidence belongs to `m02_sector_context_feature_generation`, while normalized ratio distance/slope/spread/alignment features remain in Layer 1 when the pair is broad market/cross-asset evidence.
- Source bars are canonical `1Min` rows from `m01_market_regime_data_acquisition`; `feature_generation` locally samples/aggregates them into the accepted Layer 1 input frames instead of relying on provider-native 30-minute or daily downloads.
- No provider calls.
- Runtime SQL writes are isolated in `sql.py`; the package CLI `trading-data-m01-market-regime-feature-generation` is the direct feature-generation surface and unit tests do not touch a durable database. When source reads include historical lookback for rolling daily features, inferred snapshot rows can be bounded with `--snapshot-start` / `--snapshot-end` so only the reviewed target window is emitted.
- `from_feed_artifacts.py` is the offline manager-runtime bridge for already-acquired Layer 1 Alpaca bar receipts: it reads successful `01_feed_alpaca_bars` completion receipts, confirms row counts for SQL-retained bars in `m01_market_regime_data_acquisition`, and then generates `m01_market_regime_feature_generation` rows without provider calls. It reads a historical source-bar lookback by default for rolling feature context while keeping emitted feature rows bounded to the requested month.
- No generated artifacts committed to Git.

## Key file

- `generator.py` owns feature generation, point-in-time filtering, and feature row output used by the SQL runner and tests.
- `sql.py` owns SQL reads/writes for `trading_data.m01_market_regime_data_acquisition -> trading_data.m01_market_regime_feature_generation`.
- `from_feed_artifacts.py` owns offline feature generation from SQL-retained Alpaca bar receipts. Routine saved JSONL/CSV bar artifacts are no longer part of the current route.
