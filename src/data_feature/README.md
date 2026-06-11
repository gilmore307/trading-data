# data_feature

Deterministic point-in-time feature builders owned by `trading-data`.

## Boundary

Feature packages transform accepted feed/source data into model-facing feature tables. They do not call providers directly and do not own model outputs, labels, evaluation runs, or promotion decisions.

## Packages

- `m01_market_regime_feature_generation/` — Layer 1 MarketRegimeModel feature generator and SQL runner for `trading_data.model_01_market_regime_feature_generation`; generated feature values are stored in `feature_payload_json` JSONB under the `snapshot_time + input_frame + prediction_horizon + market_universe_ref` row key. It consumes canonical `1Min` `trading_data.model_01_market_regime_data_acquisition` bars and shared CSV rows scoped to `model_layer = layer_01_market_regime`; sector/industry rotation pair features are excluded from this Layer 1 surface.
- `m02_sector_context_feature_generation/` — Layer 2 SectorContextModel sector/industry rotation feature generator and SQL runner for `trading_data.model_02_sector_context_feature_generation`; rows are keyed by `snapshot_time + candidate_symbol + comparison_symbol + rotation_pair_id` and store relative-strength plus sector-observation summary evidence in `feature_payload_json`. It derives 30-minute and daily evidence locally from canonical `1Min` source bars.
- `m03_target_state_vector_feature_generation/` — active contract-first Layer 3 target state-vector feature workspace for `trading_data.model_03_target_state_vector_feature_generation` market/sector/target/cross-state feature blocks, including target-level ThetaData option-chain state reduction from `trading_data.option_chain_state_source` when available.
- `m06_residual_event_governance_feature_generation/` — M06 event-risk-governor source overview feature builder for `trading_data.model_06_residual_event_governance_feature_generation` deterministic event-category, scope, dedup, source-priority, and quality payloads; final event-risk intervention remains in `trading-model` / execution risk-control.
- `m05_option_expression_feature_generation/` — M05 option-chain candidate feature builder for `trading_data.model_05_option_expression_feature_generation` deterministic moneyness, spread/liquidity, IV, and Greeks payloads derived from shared `trading_data.option_chain_state_source`; final trading guidance / option-expression plans remain in `trading-model`.

Layers 4-7 intentionally have no `trading-data` feature package: event failure risk, alpha confidence, position projection, and underlying action features are model/control-plane surfaces, not new source-derived feature outputs in this repository.
