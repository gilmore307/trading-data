# 09_feed_thetadata_option_selection_snapshot

ThetaData option-chain selection snapshot feed.

## Purpose

Produce a point-in-time SQL `feed_09_option_chain_snapshot` row for a specified underlying and explicit ET snapshot time. The feed captures chain visibility; it does not select contracts or apply liquidity/spread/IV/Greek filters.

## Required params

- `underlying` — equity underlying symbol, e.g. `AAPL`.
- `snapshot_time` — explicit ISO datetime in `America/New_York`, e.g. `2026-04-24T16:00:00-04:00`.

No implicit latest/current mode exists. The caller must supply `snapshot_time`.

## Optional runtime params

- `output_root` — development output root at task-key top level; defaults to `storage/<task_id>`.
- `thetadata_transport` — defaults to `python_library`; set `terminal_rest` only for controlled fallback or fixture tests.
- `thetadata_base_url` — local ThetaData Terminal base URL used only by `terminal_rest`; defaults to `http://127.0.0.1:25503`.
- `thetadata_credentials_file` — optional ThetaData Python library credential file path; defaults to the local reviewed ThetaData runtime credentials file.
- `timeout_seconds` — request timeout; defaults to `30`.
- `registry_csv` — optional registry snapshot for retained registered-field validation; when missing, fixture/local runs use code-local field names without reading an external repository path.
- `historical_mode` — defaults to `true` for past dates. Historical replay uses ThetaData history endpoints instead of realtime snapshot endpoints.
- `window_start` / `window_end` — optional explicit ET window for historical replay. When omitted, the feed uses the minute containing `snapshot_time`.
- `max_dte` — maximum days to expiration for historical full-chain requests; defaults to `45`.
- `strike_range` — ThetaData strike range bound for historical full-chain requests; defaults to `5`, the current Layer 9 closed-loop bucket runtime default.
- `option_prefilter_enabled` — defaults to `true`; filters structurally invalid option quotes before final normalization.
- `option_prefilter_min_mid` — minimum quote mid retained by the structural prefilter; defaults to `0.01`.

## Source route

Default historical and current acquisition uses the official ThetaData Python library through the shared `trading-manager` Python environment. This bypasses the local Terminal REST concurrency cap and returns tabular rows that are normalized in memory into the same feed contract.

Explicit `terminal_rest` fallback uses ThetaData Terminal v3:

- Historical replay: `/v3/option/history/quote`, `/v3/option/history/trade`, and `/v3/option/history/greeks/eod`.
- Realtime/current snapshot mode: `/v3/option/snapshot/quote`, `/v3/option/snapshot/greeks/implied_volatility`, and `/v3/option/snapshot/greeks/first_order`.

Historical requests pass underlying, wildcard expiration, snapshot date, a bounded ET time window, `max_dte`, and `strike_range`. The final artifact uses contract-level minute clocks for historical windows while keeping the top-level `snapshot_time` as the request clock.

## Outputs

```text
<output_root>/runs/<run_id>/
  request_manifest.json
  schema.json
  trading_data.feed_09_option_chain_snapshot
<output_root>/completion_receipt.json
```

Only the normalized final SQL row is saved. Raw provider responses are normalized in memory and discarded by default.

Key row fields include underlying, snapshot time, contract identity, quote, IV, first-order Greeks, trade summary, and derived/context fields where provider data is available.

## Failure and retry

The final SQL write is atomic. A failed run has no valid partial final output; rerun the task after fixing the cause.
