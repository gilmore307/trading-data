# Layer 07 - Underlying Action Data

`trading-data` does not own a dedicated Layer 7 source. This is intentional.

Layer 7 is `UnderlyingActionModel` in `trading-model`. It evaluates offline action context after upstream model states and position projection are available. It is not a provider acquisition or source-normalization layer.

## Owned artifact

```text
none in trading-data
```

## Boundary

Layer 7 may consume:

- `position_projection_vector` from Layer 6;
- upstream context/model outputs;
- reviewed model-side evaluation artifacts;
- action-policy context owned outside `trading-data`.

`trading-data` supplies only upstream observed data and deterministic features. It does not choose final underlying actions.

## Stage flow

```text
position_projection_vector + upstream context
  -> trading-model UnderlyingActionModel
  -> offline underlying-action recommendation context
  -> expression/execution boundaries outside trading-data
```

## Non-ownership

`trading-data` must not emit:

- buy/sell/hold decisions;
- action recommendations;
- trade intent;
- order type;
- broker mutation;
- account-level execution state.

## Acceptance notes

A Layer 7-related `trading-data` change is acceptable only if it introduces a real point-in-time observed data input required by an accepted upstream source/feature contract. Action selection and evaluation belong in `trading-model` and the control-plane repositories.
