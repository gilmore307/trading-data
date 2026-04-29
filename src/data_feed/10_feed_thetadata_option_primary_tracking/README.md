# 10_feed_thetadata_option_primary_tracking

ThetaData specified-contract option primary tracking feed.

## Purpose

Produce final `option_bar.csv` rows for one option contract supplied in the task key. This feed tracks a specified contract; it does not select contracts. Contract selection belongs to future model work that consumes `option_chain_snapshot`.

## Input task params

Required:

- `underlying` — equity underlying symbol, e.g. `AAPL`.
- `expiration` — option expiration date, e.g. `2026-05-15`.
- `right` — `CALL` or `PUT`.
- `strike` — option strike price.
- `start_date` — ThetaData request start date, `YYYY-MM-DD`.
- `end_date` — ThetaData request end date, `YYYY-MM-DD`.
- `timeframe` — final bar grain. Supported values: `1Sec`, `1Min`, `5Min`, `15Min`, `30Min`, `1Hour`, `1Day`.

Optional development/runtime params:

- `output_root` at task-key top level — development output root. Defaults to `storage/<task_id>`.
- `thetadata_base_url` — local ThetaData Terminal base URL. Defaults to `http://127.0.0.1:25503`.
- `timeout_seconds` — request timeout. Defaults to `30`.
- `registry_csv` — optional registry snapshot used for retained registered fields; retired preview-only local output fields use code-local names and must not be re-registered. Defaults to `/root/projects/trading-main/registry/current.csv`.

## Source endpoint

The feed uses ThetaData Terminal v3:

- `/v3/option/history/ohlc`

ThetaData returns 1-second OHLC rows including zero-volume placeholder rows. The feed treats those provider rows as transient and aggregates only rows with nonzero `volume` or `count` into the requested final `timeframe`.

## Development outputs

For each run:

```text
<output_root>/runs/<run_id>/
  request_manifest.json
  cleaned/
    option_bar.jsonl
    schema.json
  saved/
    option_bar.csv
<output_root>/completion_receipt.json
```

Only `saved/option_bar.csv` is the final saved output. Cleaned JSONL is run-local/transient development evidence. Full raw provider responses are not persisted by default.

## Final CSV shape

This legacy feed interface can still emit the local development CSV shape listed below, but the old `storage/templates/data_kinds/` preview contract has been retired. Accepted model-input output contracts are now owned by dedicated SQL tables.

Fields include:

- `underlying`
- `expiration`
- `right`
- `strike`
- `timeframe`
- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `count`
- `vwap`

## Failure and retry

Development-stage save is atomic: the feed writes a temporary CSV file and renames it to `option_bar.csv` only after serialization succeeds. If the run fails, rerun the task. Durable SQL storage is future `trading-storage` work.
