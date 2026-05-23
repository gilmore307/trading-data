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

Layer 4 may reference evidence produced from accepted upstream event/feed artifacts, including reviewed event-amplified session-gap risk for overnight, weekend, holiday, halt, or other non-continuous-market holding windows. The reviewed promotion gate, model vector, labels, and production-readiness decision belong outside this repository.

`trading-data` may only add Layer 4 data work when a reviewed contract requires a real point-in-time source observation or deterministic feature package. It must not automatically promote Layer 10 research events into Layer 4.

## Event partitions and retention

Any accepted Layer 4 data work must keep event evidence split into:

- global/common event context: macro data releases, broad market policy/geopolitical/rates/liquidity events, sector or industry news, and other reusable context for all targets or sector baskets;
- target event context: symbol/issuer/target-specific news, SEC filings, earnings/guidance artifacts, same-symbol option events, corporate actions, and other target-scoped evidence.

Training-fold cleanup may remove only the fold-local target event working set for the completed or abandoned fold. It must not remove global/common event rows, shared macro/sector/political evidence, reviewed global event-family packets, or reusable event references. Fold-local target data should reference global event rows instead of copying them into a namespace that lifecycle cleanup can delete.

## Non-ownership

`trading-data` must not emit:

- `event_failure_risk_vector` scores;
- alpha confidence scores;
- target exposure or position sizing;
- underlying/action/option decisions;
- broker/account mutations;
- production promotion decisions.
