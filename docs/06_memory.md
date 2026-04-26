# Memory

## Durable Local Notes

- `trading-data` is the upstream data producer, not a strategy/model/execution/dashboard repository.
- Generated datasets, provider dumps, logs, notebooks, credentials, and secrets must stay out of Git.
- Shared fields, statuses, type values, helper surfaces, and reusable templates discovered here must be routed to `trading-main` for registry/docs review.
- Durable storage layout and retention are owned by `trading-storage`; do not hard-code final layout assumptions before those contracts exist.
- Default tests should avoid live provider calls unless explicitly guarded.
- Market-state discovery belongs in `trading-model`; `trading-data` may emit market/data-source features but must not use strategy returns or profitability as upstream data inputs.
- Current planning domains are market board data / 盘面数据, instrument data / 标的数据, and option data / 期权数据; they correspond to later model lanes but are not model logic.
- Data-source connectors are the first implementation layer; provider tokens/API keys live under `/root/secrets/` and are referenced by aliases, not stored in this repository.
- `trading-data` input is a task instruction from `trading-manager`; output is cleaned data artifacts plus manifests/ready signals after contracts are accepted.
- OKX is the first registered crypto provider config surface. Use `trading-main` config alias `okx` / `OKX_SECRET_ALIAS`, backed by `/root/secrets/okx.json` with fields `api_key`, `secret_key`, and `passphrase`; do not copy secret values into this repo.
