# 09_feed_thetadata_option_selection_snapshot

ThetaData option-chain selection snapshot feed.

## Purpose

Produce a point-in-time `option_chain_snapshot.csv` artifact for a specified underlying and explicit ET snapshot time. The feed captures chain visibility; it does not select contracts or apply liquidity/spread/IV/Greek filters.

## Required params

- `underlying` — equity underlying symbol, e.g. `AAPL`.
- `snapshot_time` — explicit ISO datetime in `America/New_York`, e.g. `2026-04-24T16:00:00-04:00`.

No implicit latest/current mode exists. The caller must supply `snapshot_time`.

## Optional runtime params

- `output_root` — development output root at task-key top level; defaults to `storage/<task_id>`.
- `thetadata_base_url` — local ThetaData Terminal base URL; defaults to `http://127.0.0.1:25503`.
- `timeout_seconds` — request timeout; defaults to `30`.
- `registry_csv` — optional registry snapshot for retained registered-field validation; when missing, fixture/local runs use code-local field names without reading an external repository path.
- `historical_mode` — defaults to `true` for past dates. Historical replay uses ThetaData history endpoints instead of realtime snapshot endpoints.
- `max_dte` — maximum days to expiration for historical full-chain requests; defaults to `45`.
- `strike_range` — ThetaData strike range bound for historical full-chain requests; defaults to `5`, the current Layer 9 closed-loop bucket runtime default.

## Source endpoints

ThetaData Terminal v3:

- Historical replay: `/v3/option/history/quote` and `/v3/option/history/greeks/eod`.
- Realtime/current snapshot mode: `/v3/option/snapshot/quote`, `/v3/option/snapshot/greeks/implied_volatility`, and `/v3/option/snapshot/greeks/first_order`.

Historical requests pass underlying, wildcard expiration, snapshot date, a bounded one-minute ET time window, `max_dte`, and `strike_range`. The final artifact uses `snapshot_time` as the point-in-time clock.

## Outputs

```text
<output_root>/runs/<run_id>/
  request_manifest.json
  saved/
    option_chain_snapshot.csv
<output_root>/completion_receipt.json
```

Only the normalized final CSV is saved. Raw provider responses are normalized in memory and discarded by default.

Key row fields include underlying, snapshot time, contract identity, quote, IV, first-order Greeks, and derived/context fields where provider data is available.

## Failure and retry

The final CSV write is atomic. A failed run has no valid partial final output; rerun the task after fixing the cause.
