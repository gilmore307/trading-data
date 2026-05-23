# Layer 06 Dynamic Risk Policy Data Boundary

Status: active 10-layer architecture. Layer 6 owns DynamicRiskPolicyModel inputs and state calibration, but `trading-data` does not own a dedicated Layer 6 source or feature package.

Dynamic risk policy is learned from global market regime, broad event-risk context, Layer 5 alpha confidence, and portfolio/account replay state. Those inputs are owned by upstream model/control-plane/execution boundaries. This layer must not introduce target-specific hard risk-limit data or per-symbol policy surfaces that would distort policy from isolated symbols or sectors.

Layer 6 also owns base trading-calendar/session-closure exposure. Predictable non-trading intervals are not raw event evidence and do not require a dedicated Layer 6 source package by default, but upstream data/runtime helpers must preserve enough point-in-time calendar evidence for model-side risk calibration.

Accepted local shape:

```text
no source_06_dynamic_risk_policy
no feature_06_dynamic_risk_policy
```

`trading-data` may support this layer only by preserving point-in-time availability, source provenance, and deterministic upstream features already owned by other layers. Order hard limits remain execution/order-gateway controls, not model-input data products.

Acceptable future support for Layer 6 calendar risk includes deterministic exchange-calendar/session fields such as:

```text
next_market_open_time
non_trading_interval_minutes
closure_type
closure_length_bucket
holiday_name
early_close_flag
pre_holiday_session_flag
calendar_gap_risk_source_ref
```

The expected base risk ordering is intraday/same-session exposure below ordinary overnight, below weekend, below market holiday/long-weekend, below major long-holiday closure such as Thanksgiving or Christmas. `trading-data` preserves the calendar facts; `trading-model` owns the risk score and calibration.
