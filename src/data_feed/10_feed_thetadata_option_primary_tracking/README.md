# 10_feed_thetadata_option_primary_tracking

ThetaData specified-contract option bar feed.

## Purpose

Produce final SQL `feed_10_option_bar` rows for one option contract supplied by the caller. The feed tracks the supplied contract; it does not choose contracts.

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
- `thetadata_transport` — defaults to `python_library`; set `terminal_rest` only for controlled fallback or fixture tests.
- `thetadata_base_url` — local ThetaData Terminal base URL used only by `terminal_rest`; defaults to `http://127.0.0.1:25503`.
- `thetadata_credentials_file` — optional ThetaData Python library credential file path; defaults to the local reviewed ThetaData runtime credentials file.
- `timeout_seconds` — request timeout; defaults to `30`.
- `registry_csv` — optional registry snapshot for retained registered-field validation; when missing, fixture/local runs use code-local field names without reading an external repository path.

## Source route

Default historical acquisition uses the official ThetaData Python library through the shared `trading-manager` Python environment:

- `option_history_ohlc`

The feed requests the supplied exact `symbol + expiration + strike + right` contract and regular-session OHLC rows, then aggregates active rows to the requested `America/New_York` timeframe.

Explicit `terminal_rest` fallback uses ThetaData Terminal v3:

- `/v3/option/history/ohlc`

ThetaData may return zero-volume placeholders. The feed treats provider rows as transient, skips zero-volume/count placeholders, and aggregates active rows to the requested `America/New_York` timeframe.

## Outputs

```text
<output_root>/runs/<run_id>/
  request_manifest.json
  schema.json
  trading_data.feed_10_option_bar
<output_root>/completion_receipt.json
```

Only `trading_data.feed_10_option_bar` is the final saved output. Raw provider responses are not persisted by default.

Final SQL fields include contract identity, timeframe, timestamp, OHLC, volume, trade count, and VWAP.

## Failure and retry

The final SQL write is atomic. A failed run has no valid partial final output; rerun the task after fixing the cause.
