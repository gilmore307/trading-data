# Layer 06 Dynamic Risk Policy Data Boundary

Status: active 10-layer architecture. Layer 6 owns DynamicRiskPolicyModel inputs and state calibration, but `trading-data` does not own a dedicated Layer 6 source or feature package.

Dynamic risk policy is learned from global market regime, accepted event-risk pressure, Layer 5 alpha confidence, and portfolio/account replay state. Those inputs are owned by upstream model/control-plane/execution boundaries. This layer must not introduce target-specific hard risk-limit data or per-symbol policy surfaces that would distort policy from isolated symbols or sectors.

Layer 6 does not own raw trading-calendar or market-structure event interpretation. Calendar/structure dates such as overnight/weekend/holiday closures, early closes, triple-witching, major option-expiry windows, index reconstitution, or Nasdaq-100 rebalance belong to Layer 4 once reviewed as scheduled event-risk families. Layer 6 consumes the accepted Layer 4 / Layer 5 pressure when calibrating budgets.

Accepted local shape:

```text
no source_06_dynamic_risk_policy
no feature_06_dynamic_risk_policy
```

`trading-data` may support this layer only by preserving point-in-time availability, source provenance, and deterministic upstream features already owned by other layers. Order hard limits remain execution/order-gateway controls, not model-input data products.

Calendar/session facts may still be preserved by data/runtime helpers for Layer 4 evidence and downstream audit, for example:

```text
next_market_open_time
non_trading_interval_minutes
closure_type
closure_length_bucket
holiday_name
early_close_flag
pre_holiday_session_flag
expiry_or_rebalance_flag
calendar_event_source_ref
```

The expected prior ordering is intraday/same-session exposure below ordinary overnight, below weekend, below market holiday/long-weekend, below major long-holiday closure such as Thanksgiving or Christmas. `trading-data` preserves the point-in-time calendar facts; `trading-model` owns whether the accepted relationship belongs in Layer 4 and how Layer 6 consumes the resulting risk pressure.
