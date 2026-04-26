# Memory

## Durable Local Notes

- `trading-data` is the upstream data producer, not a strategy/model/execution/dashboard repository.
- Generated datasets, provider dumps, logs, notebooks, credentials, and secrets must stay out of Git.
- Shared fields, statuses, type values, helper surfaces, and reusable templates discovered here must be routed to `trading-main` for registry/docs review.
- Durable storage layout and retention are owned by `trading-storage`; do not hard-code final layout assumptions before those contracts exist.
- Default tests should avoid live provider calls unless explicitly guarded.
- Market-state discovery belongs in `trading-model`; `trading-data` may emit market/data-source features but must not use strategy returns or profitability as upstream data inputs.
