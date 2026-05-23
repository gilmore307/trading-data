# source_01_market_regime

Market-context ETF bar source for Layer 1 market regime and Layer 2 sector context.

This source fetches the reviewed market/sector/cross-asset ETF universe over a manager-supplied time range and writes one normalized SQL long table. Stable defaults live in the pipeline code; there is no source-local `config.json` for this contract. Layer ownership is not inferred from the source table name; downstream feature generators must honor the shared CSV `model_layer` discriminator.

## Input parameters

The manager supplies these values in `task_key.params`:

- `start` — required. Inclusive provider request start timestamp/date.
- `end` — required. Exclusive/provider request end timestamp/date.
- `symbols` — optional debug/review subset. String comma list or JSON list of symbols from the reviewed universe.
- `market_regime_etf_universe_path` — optional reviewed override. Normal runs use `TRADING_STORAGE_REPO_ROOT/main/shared/layer_01_02_market_context_etf_universe.csv`, defaulting to the sibling `trading-storage` repository.
- `limit`, `max_pages`, `adjustment`, `feed`, `timeout_seconds`, `secret_alias` — optional request/runtime overrides.

The task key also carries orchestration fields outside `params`, including `task_id`, `source = "source_01_market_regime"`, and optional `output_root` for receipts/manifests.

## Universe contract

The universe CSV owns ETF scope and grain choices:

- `symbol` — ETF symbol to fetch.
- `universe_type` / `exposure_type` — why the ETF belongs in the universe.
- `model_layer` — authoritative scope discriminator; `layer_01_market_regime` rows feed Layer 1 feature construction and `layer_02_sector_context` rows feed Layer 2 sector/industry/theme observation.
- `feature_grain` — downstream observation/feature grain cue for that ETF, e.g. `1d`, `30m`. It is not a provider download grain.
- `fund_name`, `issuer_name` — human-readable metadata.

`source_01_market_regime` downloads one canonical raw bar stream: `1Min`. Multi-frame market and sector evidence is derived during feature generation from those 1-minute source rows. The source stage rejects non-`1Min` task-key timeframes so the table does not mix provider-native 1-minute, 30-minute, and daily bars.

## Output format

Final saved artifact is SQL-only:

```text
source_01_market_regime
```

Driver: PostgreSQL using the shared trading-data SQL storage target. Tests inject a fake writer; local SQLite is not the accepted production contract.

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

All configured ETFs are stored in the same long table using `timeframe = 1Min`. Downstream feature code must explicitly aggregate or sample those rows for `1min`, `5min`, `30min`, and `1d` feature surfaces; provider-native multi-frame rows must not be introduced into this source table.

Run metadata:

- request manifest: `<output_root>/runs/<run_id>/request_manifest.json`
- completion receipt: `<output_root>/completion_receipt.json`

No CSV, cleaned JSONL, or SQLite database is written for this accepted SQL output.
