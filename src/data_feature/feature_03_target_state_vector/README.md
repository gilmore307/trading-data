# feature_03_target_state_vector

Contract-first workspace for deterministic Layer 3 target state-vector feature production.

This is the active replacement target for the legacy `feature_03_strategy_selection` runner. It should build point-in-time feature rows for `TargetStateVectorModel`; it must not simulate strategy variants or make model promotion decisions.

## Intended table

```text
trading_data.feature_03_target_state_vector
```

## V1 feature blocks

The feature surface should expose the same four model-facing blocks used by `trading-model`:

- `market_state_features`
- `sector_state_features`
- `target_state_features`
- `cross_state_features`

The first implementation may store these as JSON payloads for review, but the block names should remain inspectable in SQL output and receipts.

## Required row keys

- `available_time`
- `tradeable_time`
- `target_candidate_id`
- `market_context_state_ref`
- `sector_context_state_ref`
- `feature_vector_version`
- `source_run_ref`

## Non-ownership

This package does not own target-state labels, model training, state clustering, promotion decisions, strategy selection, option contracts, position sizing, execution, or portfolio allocation.
