# Layer 06 Dynamic Risk Policy Data Boundary

Status: active 10-layer architecture. Layer 6 owns DynamicRiskPolicyModel inputs and state calibration, but `trading-data` does not own a dedicated Layer 6 source or feature package.

Dynamic risk policy is learned from global market regime, broad event-risk context, Layer 5 alpha confidence, and portfolio/account replay state. Those inputs are owned by upstream model/control-plane/execution boundaries. This layer must not introduce target-specific hard risk-limit data or per-symbol policy surfaces that would distort policy from isolated symbols or sectors.

Accepted local shape:

```text
no source_06_dynamic_risk_policy
no feature_06_dynamic_risk_policy
```

`trading-data` may support this layer only by preserving point-in-time availability, source provenance, and deterministic upstream features already owned by other layers. Order hard limits remain execution/order-gateway controls, not model-input data products.
