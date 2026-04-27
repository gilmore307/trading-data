# thetadata_option_selection_snapshot

ThetaData option-chain selection snapshot bundle.

## Purpose

Produce a point-in-time `option_chain_snapshot` final JSON artifact for a specified underlying and explicit ET snapshot time. The output is used as future option-selection model input. This bundle does not select contracts and does not filter by liquidity, spread, bid/ask availability, IV, or Greeks availability.

## Input task params

Required:

- `underlying` — equity underlying symbol, e.g. `AAPL`.
- `snapshot_time_et` — explicit ISO datetime in `America/New_York`, e.g. `2026-04-24T16:00:00-04:00`.

Optional development/runtime params:

- `output_root` at task-key top level — development output root. Defaults to `data/storage/<task_id>`.
- `thetadata_base_url` — local ThetaData Terminal base URL. Defaults to `http://127.0.0.1:25503`.
- `timeout_seconds` — request timeout. Defaults to `30`.
- `registry_csv` — registry snapshot used to resolve stable field/data-kind ids. Defaults to `/root/projects/trading-main/registry/current.csv`.

No implicit latest/current snapshot mode is supported. The caller must supply `snapshot_time_et`.

## Source endpoints

The bundle uses ThetaData Terminal v3 snapshot endpoints:

- `/v3/option/snapshot/quote`
- `/v3/option/snapshot/greeks/implied_volatility`
- `/v3/option/snapshot/greeks/first_order`

The request passes the underlying, wildcard expiration, `date`, and ET `ms_of_day` derived from `snapshot_time_et`. Provider snapshot rows may carry per-contract timestamps that differ slightly from the requested context; the final artifact preserves those per-contract ET timestamps.

## Development outputs

For each run:

```text
<output_root>/runs/<run_id>/
  request_manifest.json
  saved/
    option_chain_snapshot.json
<output_root>/completion_receipt.json
```

Only the normalized final JSON is saved. Full raw provider responses are not persisted by default.

## Final JSON shape

The output follows `templates/data_kinds/thetadata/option_chain_snapshot.preview.json` and is generated with field names resolved from stable `trading-main` registry ids.

Top-level fields include:

- `data_kind`
- `source`
- `underlying`
- `snapshot_time_et`
- `contract_count`
- `contracts`

Each contract includes expiration/right/strike plus nested quote, IV, Greeks, derived, and underlying context where provider data is available.

## Failure and retry

Development-stage save is atomic: the bundle writes a temporary JSON file and renames it to `option_chain_snapshot.json` only after serialization succeeds. If the run fails, rerun the task; no partial final JSON is considered valid.

Durable SQL storage is future `trading-storage` work. The accepted direction is to store this nested final artifact in a PostgreSQL `jsonb` column, not as an external JSON file path.
