# Layer 04 — Event Failure Risk Data Boundary

<!-- ACTIVE_LAYER_REVISION -->
Status: active architecture revision. `trading-data` owns no dedicated Layer 4 source/feature package by default; `EventFailureRiskModel` belongs to `trading-model` and consumes reviewed event/strategy-failure gates plus point-in-time evidence references.
<!-- /ACTIVE_LAYER_REVISION -->

Layer 4 is `EventFailureRiskModel`. It conditions alpha confidence using agent-reviewed event/strategy-failure relationships. It is not a raw-news ingestion layer and must not create a symmetry-only `trading-data` source or feature surface.

Layer 4 is the quantitative event-failure-risk model. `trading-data` may preserve point-in-time event observation rows and support refs for Layer 4, but it does not decide whether an event relationship exists, whether a co-event caused the failure, or how much risk Layer 4 should score.

Trading-calendar and market-structure dates are scheduled event-family evidence for Layer 4 when they can change liquidity, de-risking, forced flow, gap behavior, or path risk. Ordinary overnight, Friday/weekend de-risking, holiday and long-weekend closures, early closes, Thanksgiving/Christmas closures, triple-witching, major option-expiry windows, index reconstitution, Nasdaq-100 rebalance, and similar dates remain observation evidence until a reviewed Layer 10/Layer 4 supervision packet accepts the relationship.

## Owned artifact

```text
none in trading-data
```

## Boundary

Layer 4 may reference evidence produced from accepted upstream event/feed artifacts, including reviewed calendar/market-structure session-gap risk for overnight, weekend, holiday, expiry, rebalance, halt, or other non-continuous-market windows. The reviewed promotion gate, model vector, labels, and production-readiness decision belong outside this repository.

`trading-data` may only add Layer 4 data work when a reviewed contract requires a real point-in-time source observation or deterministic feature package. It must not automatically promote Layer 10 research events into Layer 4.

Accepted Layer 4 data work must be traceable to a reviewed Layer 10/review supervision packet or training contract. Source/event rows without that reviewed route remain observation or Layer 10 research evidence, not active Layer 4 training input.

When accepted, the direct Layer 4 event-facing artifact is a point-in-time event observation row, not raw provider payloads or raw article/filing/transcript text. The observation row must carry the inference-time scope fields Layer 4 may consume:

- `event_id` / `canonical_event_id`;
- `available_time`;
- `event_family` / `normalized_event_type`;
- `expected_impact_scope`;
- `affected_scope`;
- `affected_entities`;
- `scope_confidence_score`;
- `scope_support_evidence_ref`;
- `review_status`.

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
