# Layer 06 — Position Projection Data Boundary

<!-- ACTIVE_LAYER_REVISION -->
Status: active architecture revision. `trading-data` owns no dedicated Layer 6 source/feature by default; PositionProjectionModel belongs to `trading-model` / control-plane state boundaries.
<!-- /ACTIVE_LAYER_REVISION -->


`trading-data` does not own a dedicated Layer 6 source or feature package. This is intentional.

Layer 6 is `PositionProjectionModel` in `trading-model`. It relates alpha confidence to current/pending position state, target exposure, costs, and risk-budget context. Those inputs are model/control-plane/execution-state concerns, not new historical provider acquisition owned by `trading-data`.

## Owned artifact

```text
none in trading-data
```

## Boundary

Layer 6 may consume:

- final adjusted `alpha_confidence_vector`;
- current and pending position state;
- cost/risk-budget context;
- model-side projection/evaluation artifacts.

`trading-data` may provide upstream observed market/source features used before this layer, but it does not create `feature_06_position_projection` or produce the `position_projection_vector`.

## Stage flow

```text
alpha_confidence_vector + position/risk/cost context
  -> trading-model PositionProjectionModel
  -> position_projection_vector
  -> downstream action/expression review outside trading-data
```

## Non-ownership

`trading-data` must not emit:

- target exposure;
- position projection vectors;
- account-risk allocation;
- position size;
- buy/sell/hold decisions;
- order instructions;
- broker/account mutations.

## Acceptance notes

A Layer 6-related `trading-data` change is acceptable only when it supplies real point-in-time observed data needed upstream of projection. Position state, pending orders, account exposure, cost policy, and risk-budget decisions belong outside `trading-data`.