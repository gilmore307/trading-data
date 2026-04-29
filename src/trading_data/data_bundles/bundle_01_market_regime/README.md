# bundle_01_market_regime

MarketRegimeModel manager-facing ETF bar bundle.

This bundle fetches the reviewed market/sector/cross-asset ETF universe over a manager-supplied time range and writes one normalized SQL long table. Stable defaults live in the pipeline code; there is no bundle-local `config.json` for this contract.

## Input parameters

The manager supplies these values in `task_key.params`:

- `start` — required. Inclusive provider request start timestamp/date.
- `end` — required. Exclusive/provider request end timestamp/date.
- `symbols` — optional debug/review subset. String comma list or JSON list of symbols from the reviewed universe.
- `market_etf_universe_path` — optional reviewed override. Normal runs use `/root/projects/trading-main/storage/shared/market_etf_universe.csv`.
- `limit`, `max_pages`, `adjustment`, `feed`, `timeout_seconds`, `secret_alias` — optional request/runtime overrides.

The task key also carries orchestration fields outside `params`, including `task_id`, `bundle = "bundle_01_market_regime"`, and optional `output_root` for receipts/manifests.

## Universe contract

The universe CSV owns ETF scope and grain choices:

- `symbol` — ETF symbol to fetch.
- `universe_type` / `exposure_type` — why the ETF belongs in the universe.
- `bar_grain` — requested bar grain for that ETF, e.g. `1d`, `30m`.
- `fund_name`, `issuer_name` — human-readable metadata.

## Output format

Final saved artifact is SQL-only:

```text
model_inputs.market_regime_etf_bar
```

Driver: PostgreSQL using the shared model-input storage target. Tests inject a fake writer; local SQLite is not the accepted production contract.

Table: `market_regime_etf_bar`

Columns, in order:

1. `run_id`
2. `task_id`
3. `symbol`
4. `timeframe`
5. `timestamp`
6. `open`
7. `high`
8. `low`
9. `close`
10. `volume`
11. `vwap`
12. `trade_count`
13. `created_at`

Natural key: `run_id + symbol + timeframe + timestamp`.

All configured ETFs and all configured grains are stored in the same long table. Downstream feature code must explicitly group/filter by both `symbol` and `timeframe`; daily and intraday rows must not be rolled together accidentally.

Run metadata:

- request manifest: `<output_root>/runs/<run_id>/request_manifest.json`
- completion receipt: `<output_root>/completion_receipt.json`

No CSV, cleaned JSONL, or SQLite database is written for this accepted SQL output.
