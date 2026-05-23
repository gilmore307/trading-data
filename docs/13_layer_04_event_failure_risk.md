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

Any accepted Layer 4 data work must partition event evidence by **impact scope**, not by provider, feed, document type, or article/source category. SEC filings, earnings releases, company news, macro releases, sector news, and political events can each become local or broad depending on reviewed point-in-time impact evidence.

The required storage/feature boundary is:

- global/common impact context: reviewed events whose expected impact is reusable across the market, broad sectors, industries, themes, peer groups, supply chains, index constituents, or other multi-target scopes;
- target-local impact context: reviewed events whose expected impact is limited to the current symbol, issuer, target candidate, or same-symbol instrument set.

Data artifacts must keep point-in-time `expected_impact_scope` separate from evaluation-only `realized_impact_scope_label`. The expected scope can be produced only from evidence available at `available_time`, prior reviewed event-family rules, and contemporaneous issuer/sector/index/peer/supply-chain metadata. The realized scope is a later label for calibration/review and must not be fed back into the same fold as an inference fact.

When `trading-data` is asked to produce deterministic Layer 4 source observations or feature packages, impact-scope evidence must be joinable to the current state stack at the event `available_time`:

- Layer 1 market context for broad regime, stress, liquidity, breadth, dispersion, correlation/crowding, and transition-risk comparison;
- Layer 2 sector/industry/theme/peer context for affected basket behavior, trend stability, relative strength, correlation, and tradability comparison;
- Layer 3 target context for target-specific liquidity, path/tradability, residual behavior, state-transition quality, and target-vs-sector/market alignment.

Data work should preserve candidate scope support rows or references for market/global, sector/industry/theme, peer/supply-chain/index basket, and target-local impact. These rows are evidence for a reviewed scope resolver; they are not permission to use future reaction windows as current-fold input facts.

Training-fold cleanup may remove only the fold-local target event working set for the completed or abandoned fold. It must not remove global/common impact rows, reviewed global event-family packets, reusable cross-target evidence, or shared event references. Fold-local target data should reference global/common impact rows instead of copying them into a namespace that lifecycle cleanup can delete.

## Non-ownership

`trading-data` must not emit:

- `event_failure_risk_vector` scores;
- alpha confidence scores;
- target exposure or position sizing;
- underlying/action/option decisions;
- broker/account mutations;
- production promotion decisions.
