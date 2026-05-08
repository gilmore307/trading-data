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
- `registry_csv` — optional registry snapshot for retained registered fields; defaults to `/root/projects/trading-manager/scripts/registry/current.csv`.

## Source endpoints

ThetaData Terminal v3:

- `/v3/option/snapshot/quote`
- `/v3/option/snapshot/greeks/implied_volatility`
- `/v3/option/snapshot/greeks/first_order`

The request passes underlying, wildcard expiration, `date`, and ET `ms_of_day` derived from `snapshot_time`. The final artifact uses `snapshot_time` as the point-in-time clock.

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
