# Layer 05 - Alpha Confidence Data

`trading-data` does not own a dedicated Layer 5 source. This is intentional.

Layer 5 is `AlphaConfidenceModel` in `trading-model`. It consumes accepted upstream context/model outputs and evaluated outcome evidence; it does not require a new provider acquisition route in `trading-data` by default.

## Owned artifact

```text
none in trading-data
```

## Boundary

`AlphaConfidenceModel` consumes model-side inputs such as:

- `target_context_state` from Layer 3;
- `event_context_vector` from Layer 4;
- upstream market/sector/target context references;
- realized outcomes and labels through reviewed evaluation contracts.

Those are not new `trading-data` source acquisitions. Labels, calibration, training rows, model outputs, and promotion decisions belong outside this repository.

## Stage flow

```text
accepted Layer 1-4 outputs and references
  -> trading-model AlphaConfidenceModel
  -> alpha_confidence_vector
  -> model-side evaluation/promotion review
```

## Non-ownership

`trading-data` must not create a symmetry-only `source_05_alpha_confidence` just because Layer 5 exists. It also must not emit:

- alpha confidence scores;
- return labels;
- buy/sell/hold decisions;
- target exposure;
- position size;
- option contract selection;
- production promotion decisions.

## Acceptance notes

A Layer 5-related `trading-data` change is acceptable only if it introduces a real external/source observation or deterministic point-in-time feature needed by an accepted contract. Otherwise the work belongs in `trading-model`, `trading-manager`, or `trading-storage`.
