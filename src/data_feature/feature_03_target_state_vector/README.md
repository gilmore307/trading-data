# feature_03_target_state_vector

Deterministic Layer 3 target state-vector feature production.

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

The first implementation stores these as Python dictionaries ready for JSON/JSONB persistence by a later SQL wrapper. Block names remain inspectable in output rows and receipts.

## Current implementation

`generator.py` consumes candidate-mapped target-local bars plus optional point-in-time market/sector context rows and emits one row per `target_candidate_id + available_time` with the four V1 blocks.

V1 sparse trailing windows:

```text
5min, 15min, 60min, 390min
```

These are state observation windows, not strategy variants.

## Required row keys

- `available_time`
- `tradeable_time`
- `target_candidate_id`
- `market_context_state_ref`
- `sector_context_state_ref`
- `target_state_vector_version`
- `source_run_ref`

## Non-ownership

This package does not own target-state labels, model training, state clustering, promotion decisions, strategy selection, option contracts, position sizing, execution, or portfolio allocation.
