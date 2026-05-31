# feature_10_event_risk_governor

Deterministic event-overlay feature builder for Layer 10 event-risk-governor inputs.

## Boundary

Input is accepted `m10_event_risk_governor_data_acquisition` overview rows. Output is a compact
feature surface keyed by `event_id` for `EventRiskGovernor` / `EventIntelligenceOverlay`
input preparation. The package name is the accepted physical feature package for
this boundary.

This package does not score alpha, decide event impact, create labels, or build
the final `event_risk_intervention` / event vector; those belong to
`trading-model` and execution risk-control boundaries.

## Output table

```text
trading_data.feature_10_event_risk_governor
```

Rows carry event identity, availability clocks, and JSONB payload blocks with
point-in-time categorical/quality features derived from source overview rows.
