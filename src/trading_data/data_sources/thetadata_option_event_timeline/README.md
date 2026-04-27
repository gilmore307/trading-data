# thetadata_option_event_timeline

ThetaData option activity event timeline bundle.

## Purpose

Produce news-like `option_activity_event.csv` rows and one compact `<id>.json` detail artifact for each triggered option activity event. This bundle reports events only; it does not save rolling-window process state, raw trade/quote rows, or periodic chain snapshots by default.

## Input task params

Required:

- `underlying` — equity underlying symbol, e.g. `AAPL`.
- `expiration` — option expiration date, e.g. `2026-05-15`.
- `right` — `CALL` or `PUT`.
- `strike` — option strike price.
- `start_date` — ThetaData request start date, `YYYY-MM-DD`.
- `end_date` — ThetaData request end date, `YYYY-MM-DD`.
- `timeframe` — event evidence-window grain. Supported values: `1Min`, `5Min`, `15Min`, `30Min`, `1Hour`, `1Day`.
- `current_standard` — event-time standard values used to emit events. This is task/model/run input, not a global fixed rule.

`current_standard` can include:

```json
{
  "standard_context": {
    "standard_source": "task_key_current_standard",
    "standard_id": "opt_evt_std_Q5M8T2K1",
    "standard_generated_at_et": "2026-04-24T09:30:00-04:00"
  },
  "trade_at_ask": {
    "max_price_vs_ask": 0.01,
    "min_ask_touch_ratio": 0.95
  },
  "opening_activity": {
    "min_window_volume": 100,
    "min_volume_percentile_20d_same_time": null
  },
  "iv_high_cross_section": {
    "min_iv_percentile_by_expiration": 0.95,
    "min_iv_zscore_by_expiration": 2.0
  }
}
```

Optional params:

- `output_root` at task-key top level — development output root. Defaults to `storage/<task_id>`.
- `thetadata_base_url` — local ThetaData Terminal base URL. Defaults to `http://127.0.0.1:25503`.
- `timeout_seconds` — request timeout. Defaults to `30`.
- `registry_csv` — registry snapshot used to resolve stable field/data-kind ids. Defaults to `/root/projects/trading-main/registry/current.csv`.
- `max_events` — cap emitted events for bounded development runs. Defaults to `100`.
- `iv_context` — optional event-local IV context values. When supplied, `iv_high_cross_section` can trigger and is included in detail artifacts.

## Source endpoint

The bundle uses ThetaData Terminal v3:

- `/v3/option/history/trade_quote`

Rows are transient. The bundle groups them into ET evidence windows and emits a final event only when at least one indicator in `current_standard` is satisfied.

## Development outputs

For each run:

```text
<output_root>/runs/<run_id>/
  request_manifest.json
  cleaned/
    option_activity_event.jsonl
    schema.json
  saved/
    option_activity_event.csv
    <event_id>.json
<output_root>/completion_receipt.json
```

Only `saved/option_activity_event.csv` and `saved/<event_id>.json` are final saved outputs. Cleaned JSONL is run-local/transient development evidence. Full raw provider responses are not persisted by default.

## Final shapes

The CSV output follows `storage/templates/data_kinds/thetadata/option_activity_event.preview.csv`. Detail artifacts follow `storage/templates/data_kinds/thetadata/option_activity_event_detail.preview.json`. Field names are resolved from stable `trading-main` registry ids.

## Failure and retry

Development-stage saves are atomic: the bundle writes temporary CSV/JSON files and renames them only after serialization succeeds. Durable SQL storage is future `trading-storage` work.
