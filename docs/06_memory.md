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
- OKX is the first registered crypto provider config surface. Use `trading-main` config alias `okx` / `OKX_SECRET_ALIAS`, backed by `/root/secrets/okx.json` with fields `api_key`, `secret_key`, `passphrase`, `allowed_ip_address`, and `api_key_remark_name`; do not copy secret values into this repo.
- Alpaca is the first registered stock/ETF data provider config surface for bars, quotes, trades, and news. Use `trading-main` config alias `alpaca` / `ALPACA_SECRET_ALIAS`, backed by `/root/secrets/alpaca.json` with fields `api_key`, `secret_key`, and `endpoint`; do not copy secret values into this repo.
- ThetaData is the registered options-data provider term for chain timeline, quote, trade, OHLC, Greeks, and related options datasets. Its connector/JAR/creds.txt layout is intentionally deferred; never commit `creds.txt` or credentials.
- FRED, Census, BEA, and BLS are registered economic/macro provider config surfaces. Use `trading-main` aliases `fred`, `census`, `bea`, and `bls`, each backed by `/root/secrets/<source>.json` with field `api_key`; do not copy secret values into this repo.
- Registered provider term `path` values hold public documentation URLs; `*_SECRET_ALIAS` config `path` values still point to local source-secret JSON files.
