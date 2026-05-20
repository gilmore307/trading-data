# Layer 04 — Event Failure Risk Data Boundary

<!-- ACTIVE_LAYER_REVISION -->
Status: active architecture revision. `trading-data` owns no dedicated Layer 4 source/feature package by default; `EventFailureRiskModel` belongs to `trading-model` and consumes reviewed event/strategy-failure gates plus point-in-time evidence references.
<!-- /ACTIVE_LAYER_REVISION -->

Layer 4 is `EventFailureRiskModel`. It conditions alpha confidence using agent-reviewed event/strategy-failure relationships. It is not a raw-news ingestion layer and must not create a symmetry-only `trading-data` source or feature surface.

## Owned artifact

```text
none in trading-data
```

## Boundary

Layer 4 may reference evidence produced from accepted upstream event/feed artifacts, but the reviewed promotion gate, model vector, labels, and production-readiness decision belong outside this repository.

`trading-data` may only add Layer 4 data work when a reviewed contract requires a real point-in-time source observation or deterministic feature package. It must not automatically promote Layer 10 research events into Layer 4.

## Non-ownership

`trading-data` must not emit:

- `event_failure_risk_vector` scores;
- alpha confidence scores;
- target exposure or position sizing;
- underlying/action/option decisions;
- broker/account mutations;
- production promotion decisions.
