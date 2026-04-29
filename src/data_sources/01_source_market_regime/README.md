# 01_source_market_regime

MarketRegimeModel manager-facing ETF bar source.

This source fetches the reviewed market/sector/cross-asset ETF universe over a manager-supplied time range and writes one normalized SQL long table. Stable defaults live in the pipeline code; there is no source-local `config.json` for this contract.

## Input parameters

The manager supplies these values in `task_key.params`:

- `start` — required. Inclusive provider request start timestamp/date.
- `end` — required. Exclusive/provider request end timestamp/date.
- `symbols` — optional debug/review subset. String comma list or JSON list of symbols from the reviewed universe.
- `market_etf_universe_path` — optional reviewed override. Normal runs use `/root/projects/trading-main/storage/shared/market_etf_universe.csv`.
- `limit`, `max_pages`, `adjustment`, `feed`, `timeout_seconds`, `secret_alias` — optional request/runtime overrides.

The task key also carries orchestration fields outside `params`, including `task_id`, `source = "01_source_market_regime"`, and optional `output_root` for receipts/manifests.

## Universe contract

The universe CSV owns ETF scope and grain choices:

- `symbol` — ETF symbol to fetch.
- `universe_type` / `exposure_type` — why the ETF belongs in the universe.
- `bar_grain` — requested bar grain for that ETF, e.g. `1d`, `30m`.
- `fund_name`, `issuer_name` — human-readable metadata.

## Output format

Final saved artifact is SQL-only:

```text
source_01_market_regime
```

Driver: PostgreSQL using the shared trading-source SQL storage target. Tests inject a fake writer; local SQLite is not the accepted production contract.

Table: `source_01_market_regime`

Columns, in order:

1. `symbol`
2. `timeframe`
3. `timestamp`
4. `bar_open`
5. `bar_high`
6. `bar_low`
7. `bar_close`
8. `bar_volume`
9. `bar_vwap`
10. `bar_trade_count`

Natural key: `symbol + timeframe + timestamp`.

`run_id`, `task_id`, and write/audit timestamps live in run manifests and completion receipts, not in this business table.

All configured ETFs and all configured grains are stored in the same long table. Downstream feature code must explicitly group/filter by both `symbol` and `timeframe`; daily and intraday rows must not be rolled together accidentally.

Run metadata:

- request manifest: `<output_root>/runs/<run_id>/request_manifest.json`
- completion receipt: `<output_root>/completion_receipt.json`

No CSV, cleaned JSONL, or SQLite database is written for this accepted SQL output.
