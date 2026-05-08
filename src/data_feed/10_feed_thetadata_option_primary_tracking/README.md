# 10_feed_thetadata_option_primary_tracking

ThetaData specified-contract option bar feed.

## Purpose

Produce final `option_bar.csv` rows for one option contract supplied by the caller. The feed tracks the supplied contract; it does not choose contracts.

## Required params

- `underlying` — equity underlying symbol, e.g. `AAPL`.
- `expiration` — option expiration date, e.g. `2026-05-15`.
- `right` — `CALL` or `PUT`.
- `strike` — option strike price.
- `start_date` — ThetaData request start date, `YYYY-MM-DD`.
- `end_date` — ThetaData request end date, `YYYY-MM-DD`.
- `timeframe` — final bar grain: `1Sec`, `1Min`, `5Min`, `15Min`, `30Min`, `1Hour`, or `1Day`.

## Optional runtime params

- `output_root` — development output root at task-key top level; defaults to `storage/<task_id>`.
- `thetadata_base_url` — local ThetaData Terminal base URL; defaults to `http://127.0.0.1:25503`.
- `timeout_seconds` — request timeout; defaults to `30`.
- `registry_csv` — optional registry snapshot for retained registered fields; defaults to `/root/projects/trading-manager/scripts/registry/current.csv`.

## Source endpoint

ThetaData Terminal v3:

- `/v3/option/history/ohlc`

ThetaData returns 1-second OHLC rows, including zero-volume placeholders. The feed treats provider rows as transient, skips zero-volume/count placeholders, and aggregates active rows to the requested `America/New_York` timeframe.

## Outputs

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

Only `saved/option_bar.csv` is the final saved output. Cleaned JSONL is run-local development evidence. Raw provider responses are not persisted by default.

Final CSV fields include contract identity, timeframe, timestamp, OHLC, volume, trade count, and VWAP.

## Failure and retry

The final CSV write is atomic. A failed run has no valid partial final output; rerun the task after fixing the cause.
