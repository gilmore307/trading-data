# Memory

## Durable Local Notes

- `trading-data` is the upstream data producer, not a strategy/model/execution/dashboard repository.
- Generated datasets, provider dumps, logs, notebooks, credentials, and secrets must stay out of Git.
- Shared fields, statuses, type values, data kinds, helper surfaces, and reusable templates discovered here must be routed to `trading-main` for registry/docs review.
- Durable storage layout and retention are owned by `trading-storage`; do not hard-code final layout assumptions before those contracts exist.
- Default tests should avoid live provider calls unless explicitly guarded.
- Market-state discovery belongs in `trading-model`; `trading-data` may emit market/data-source features but must not use strategy returns or profitability as upstream data inputs.
- Current planning domains are market board data / 盘面数据, instrument data / 标的数据, and option data / 期权数据; they correspond to later model lanes but are not model logic.
- Data-source connectors are the first implementation layer; provider tokens/API keys live under `/root/secrets/` and are referenced by aliases, not stored in this repository.
- `trading-data` input is a task instruction from `trading-manager`; output is cleaned data artifacts plus manifests/ready signals after contracts are accepted.
- OKX is the first registered crypto provider config surface. Use `trading-main` config alias `okx` / `OKX_SECRET_ALIAS`, backed by `/root/secrets/okx.json` with fields `api_key`, `secret_key`, `passphrase`, `allowed_ip_address`, and `api_key_remark_name`; do not copy secret values into this repo.
- Alpaca is the first registered stock/ETF data provider config surface for bars, quotes, trades, and news. Use `trading-main` config alias `alpaca` / `ALPACA_SECRET_ALIAS`, backed by `/root/secrets/alpaca.json` with fields `api_key`, `secret_key`, and `endpoint`; do not copy secret values into this repo.
- ThetaData is the registered options-data provider term for chain timeline, quote, trade, OHLC, Greeks, and related options datasets. Use `trading-main` config alias `thetadata` / `THETADATA_SECRET_ALIAS`, backed by `/root/secrets/thetadata.json`; never commit ThetaData credentials. ThetaTerminal JAR/runtime placement remains deferred until connector design.
- FRED, Census, BEA, and BLS are registered economic/macro provider config surfaces. Use `trading-main` aliases `fred`, `census`, `bea`, and `bls`, each backed by `/root/secrets/<source>.json` with field `api_key`; do not copy secret values into this repo. For source consistency, use FRED only for FRED/St. Louis Fed/ALFRED-unique data or explicitly approved FRED-native research series/groups; use official agency sources for their own canonical measures.
- Registered provider term `path` values hold public documentation URLs; `*_SECRET_ALIAS` config `path` values still point to local source-secret JSON files.
- U.S. Treasury Fiscal Data is registered as provider term `US_TREASURY_FISCAL_DATA` with docs path `https://fiscaldata.treasury.gov/api-documentation/`; no secret alias is registered because the official docs describe the API as open/no-token.
- FOMC calendar uses the official Federal Reserve page. Official macro release calendars are found via web search but must resolve to official government/issuing-agency pages. ETF holdings stocks and weights must come from issuer websites or issuer-published holdings files.
- Workflow decision: `trading-data` handles historical data only. `trading-manager` issues a self-contained data task key file, and `trading-data` invokes the specified historical acquisition script with its parameters. During development, outputs and receipts go under ignored `storage/`; durable SQL targets and storage-resident receipts wait for accepted `trading-storage` contracts. Realtime data remains `trading-execution` scope.
- `macro_data` has been removed as an executable macro acquisition bundle. Macro model inputs now use `07_source_trading_economics_calendar_web` visible-page rows; official macro API secret aliases may remain stored for optional future research but are not active manager task routes.
- Development-stage data task outputs and receipts should be local files under ignored `storage/`, not SQL writes. SQL/durable storage is deferred until `trading-storage` contracts are accepted or an explicitly guarded integration path is approved.
- API-specific source bundles should be designed from `trading-main/templates/data_tasks/` before code: task key, bundle README, fetch spec, clean spec, save spec, completion receipt, and fixture policy. `docs/09_api_templates.md` owns the local application guide.
- Source bundles should default to one `pipeline.py` with `fetch`, `clean`, `save`, and `write_receipt` functions. Bundle-specific API details belong in each bundle README; split step functions into separate modules only when complexity justifies it.
- Keep `task_key.json` and `completion_receipt.json` minimal. Do not put provider documentation URLs or other non-consumed metadata in runtime JSON; use registry/provider docs or bundle README/specs instead.
- Data task keys are stable across periodic/scheduled runs. Per-run evidence belongs in `completion_receipt.json` under `runs[]`, with outputs under `storage/<task-id>/runs/<run-id>/`.
- All current runtime JSON fields in `task_key.json` and `completion_receipt.json` are registered in `trading-main` as `kind=field` rows with scopes `data_task_key`, `data_task_completion_receipt`, and `data_task_completion_receipt_run`. Future JSON fields need registry review.
