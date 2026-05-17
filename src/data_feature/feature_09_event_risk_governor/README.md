# feature_09_event_risk_governor

Deterministic legacy-named event-overlay feature builder for conceptual Layer 8 event-risk-governor inputs.

## Boundary

Input is accepted `source_09_event_risk_governor` overview rows. Output is a compact
feature surface keyed by `event_id` for `EventRiskGovernor` / `EventIntelligenceOverlay`
input preparation. The package name remains legacy until a dedicated physical
rename migration is accepted.

This package does not score alpha, decide event impact, create labels, or build
the final `event_risk_intervention` / event vector; those belong to
`trading-model` and execution risk-control boundaries.

## Output table

```text
trading_data.feature_09_event_risk_governor
```

Rows carry event identity, availability clocks, and JSONB payload blocks with
point-in-time categorical/quality features derived from source overview rows.
