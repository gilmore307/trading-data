# feature_04_event_overlay

Deterministic Layer 4 event-overlay feature builder.

## Boundary

Input is accepted `source_04_event_overlay` overview rows. Output is a compact
feature surface keyed by `event_id` for `EventOverlayModel` input preparation.

This package does not score alpha, decide event impact, create labels, or build
the final `event_context_vector`; those belong to `trading-model`.

## Output table

```text
trading_data.feature_04_event_overlay
```

Rows carry event identity, availability clocks, and JSONB payload blocks with
point-in-time categorical/quality features derived from source overview rows.
