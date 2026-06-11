# Layer 05 — Alpha Confidence Data Boundary

<!-- ACTIVE_LAYER_REVISION -->
Status: active architecture revision. `trading-data` owns no dedicated Layer 5 source/feature by default; AlphaConfidenceModel belongs to `trading-model` and consumes reviewed upstream state artifacts plus Layer 4 event-failure-risk outputs.

Event data does not feed Layer 5 directly. Reviewed event observations and event/strategy-failure gates feed Layer 4; broader post-failure attribution evidence feeds M06 and can affect future Layer 4 only after review.
<!-- /ACTIVE_LAYER_REVISION -->


`trading-data` does not own a dedicated Layer 5 source or feature package. This is intentional.

Layer 5 is `AlphaConfidenceModel` in `trading-model`. It consumes accepted upstream context/model outputs and evaluated outcome evidence; it does not require a new provider acquisition route in `trading-data` by default.

## Owned artifact

```text
none in trading-data
```

## Boundary

`AlphaConfidenceModel` consumes model-side inputs such as:

- `target_context_state` from Layer 3;
- upstream market/sector/target context references;
- Layer 4 `event_failure_risk_vector` when reviewed event-failure conditioning applies;
- realized outcomes and labels through reviewed evaluation contracts.

Those are not new `trading-data` source acquisitions. Labels, calibration, training rows, model outputs, and promotion decisions belong outside this repository.

## Stage flow

```text
accepted Layer 1-3 outputs and references
  -> accepted Layer 4 event_failure_risk_vector when present
  -> trading-model AlphaConfidenceModel
  -> alpha_confidence_vector
  -> model-side evaluation/promotion review
```

## Non-ownership

`trading-data` must not create a symmetry-only `source_05_alpha_confidence` or `feature_05_alpha_confidence` just because Layer 4 exists. It also must not emit:

- alpha confidence scores;
- event-failure-risk scores;
- return labels;
- buy/sell/hold decisions;
- target exposure;
- position size;
- option contract selection;
- production promotion decisions.

## Acceptance notes

A Layer 5-related `trading-data` change is acceptable only if it introduces a real external/source observation or deterministic point-in-time feature needed by an accepted contract. Otherwise the work belongs in `trading-model`, `trading-manager`, or `trading-storage`.
