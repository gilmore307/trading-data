# data_feature

Deterministic point-in-time feature builders owned by `trading-data`.

## Boundary

Feature packages transform accepted feed/source data into model-facing feature tables. They do not call providers directly and do not own model outputs, labels, evaluation runs, or promotion decisions.

## Packages

- `feature_01_market_regime/` — Layer 1 MarketRegimeModel V1 feature generator and SQL runner for `trading_data.feature_01_market_regime`; generated feature values are stored in `feature_payload_json` JSONB under the `snapshot_time` row key. Sector/industry rotation pair features are excluded from this Layer 1 surface.
- `feature_02_security_selection/` — Layer 2 SecuritySelectionModel sector/industry rotation feature generator and SQL runner for `trading_data.feature_02_security_selection`; rows are keyed by `snapshot_time + candidate_symbol + comparison_symbol + rotation_pair_id` and store relative-strength evidence in `feature_payload_json`.
