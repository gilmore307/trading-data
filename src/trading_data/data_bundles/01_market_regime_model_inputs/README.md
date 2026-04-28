# 01_market_regime_model_inputs

MarketRegimeModel manager-facing ETF bar bundle.

This bundle fetches the configured market/sector/cross-asset ETF universe over a manager-supplied time range and writes one normalized long-table bar CSV. The ETF universe, per-symbol bar grain, and stable fetch defaults live in bundle config, not in the task key.

## Input parameters

The manager supplies these values in `task_key.params`:

- `start` — required. Inclusive provider request start timestamp/date.
- `end` — required. Exclusive/provider request end timestamp/date.
- `symbols` — optional debug/review subset. String comma list or JSON list of symbols from the configured universe. Normal production runs omit this and use the full config universe.
- `config_path` — optional reviewed override for `config.json`; normal runs use this directory's bundle-local config.
- `limit`, `max_pages`, `adjustment`, `feed`, `timeout_seconds` — optional request/runtime overrides. Defaults come from config.

The task key also carries orchestration fields outside `params`, including `task_id`, `bundle = "01_market_regime_model_inputs"`, and optional `output_root`.

## Config

`config.json` owns stable facts required to complete the task but not supplied per run:

- `market_etf_universe_path` — canonical CSV containing the ETF universe. Current default: `/root/projects/trading-main/storage/shared/market_etf_universe.csv`.
- `secret_alias` — Alpaca credential source alias.
- `adjustment`, `limit`, `max_pages`, `timeout_seconds` — default request/runtime settings.
- `output` — saved artifact contract: output name, format, natural key, and columns.

The universe CSV owns the ETF scope and grain choices:

- `symbol` — ETF symbol to fetch.
- `universe_type` / `exposure_type` — why the ETF belongs in the universe.
- `bar_grain` — requested bar grain for that ETF, e.g. `1d`, `30m`.
- `fund_name`, `issuer_name` — human-readable metadata.

## Output format

Final saved artifact:

```text
<output_root>/runs/<run_id>/saved/01_market_regime_model_inputs.csv
```

Columns, in order:

1. `symbol`
2. `timeframe`
3. `timestamp`
4. `open`
5. `high`
6. `low`
7. `close`
8. `volume`
9. `vwap`
10. `trade_count`

Natural key: `symbol + timeframe + timestamp`.

All configured ETFs and all configured grains are stored in the same long table. Downstream feature code must explicitly group/filter by both `symbol` and `timeframe`; daily and intraday rows must not be rolled together accidentally.

Run metadata:

- cleaned JSONL: `<output_root>/runs/<run_id>/cleaned/01_market_regime_model_inputs.jsonl`
- cleaned schema: `<output_root>/runs/<run_id>/cleaned/schema.json`
- request manifest: `<output_root>/runs/<run_id>/request_manifest.json`
- completion receipt: `<output_root>/completion_receipt.json`
