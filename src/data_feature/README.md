# data_feature

Deterministic point-in-time feature builders owned by `trading-data`.

## Boundary

Feature packages transform accepted feed/source data into model-facing feature tables. They do not call providers directly and do not own model outputs, labels, evaluation runs, or promotion decisions.

## Packages

- `feature_01_market_regime/` — Layer 1 MarketRegimeModel feature generator and SQL runner for `trading_data.feature_01_market_regime`; generated feature values are stored in `feature_payload_json` JSONB under the `snapshot_time` row key. It consumes shared CSV rows scoped to `model_layer = layer_01_market_regime`; sector/industry rotation pair features are excluded from this Layer 1 surface.
- `feature_02_sector_context/` — Layer 2 SectorContextModel sector/industry rotation feature generator and SQL runner for `trading_data.feature_02_sector_context`; rows are keyed by `snapshot_time + candidate_symbol + comparison_symbol + rotation_pair_id` and store relative-strength plus sector-observation summary evidence in `feature_payload_json`.
- `feature_03_target_state_vector/` — active contract-first Layer 3 target state-vector feature workspace for market/sector/target/cross-state feature blocks.
- `feature_09_event_risk_governor/` — legacy-named Layer 8 event-risk-governor source overview feature builder for deterministic event-category, scope, dedup, source-priority, and quality payloads; final event-risk intervention remains in `trading-model` / execution risk-control.
- `feature_08_option_expression/` — legacy-named Layer 7 option-chain candidate feature builder for deterministic moneyness, spread/liquidity, IV, and Greeks payloads; final trading guidance / option-expression plans remain in `trading-model`.

Layers 5-7 intentionally have no `trading-data` feature package: alpha confidence, position projection, and underlying action features are model/control-plane surfaces, not new source-derived feature outputs in this repository.
