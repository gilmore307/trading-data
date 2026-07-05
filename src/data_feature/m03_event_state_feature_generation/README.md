# m03_event_state_feature_generation

Deterministic event-evidence feature builder for M03 event-state inputs.

## Boundary

Input is accepted `model_03_event_state_data_acquisition` overview rows. Output is a compact
feature surface keyed by `event_id` for M03 taxonomy and event-effect-model input
preparation. The package name is the accepted physical feature package for this boundary.

This package does not score alpha, decide event impact, create labels, emit
mean/mode/contribution shifts, or create component event-risk controls. Those
belong to `trading-model` M03/M04 and execution components.

## Output table

```text
trading_data.model_03_event_state_feature_generation
```

Rows carry event identity, availability clocks, and JSONB payload blocks with
point-in-time categorical/quality features derived from source overview rows.
