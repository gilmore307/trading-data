# 07_event_overlay_model_inputs

Manager-facing EventOverlayModel data bundle.

Layer 07 supplies bounded, point-in-time event overview rows for the event overlay model. The output is one SQL table and one row per event. Full news text, SEC filing detail, and detector artifacts stay behind references such as web URLs, SEC file paths, or internal artifact paths.

Stable defaults live in pipeline code; there is no bundle-local `config.json`.

## Input parameters

Required task key fields:

- `bundle`: `07_event_overlay_model_inputs`
- `task_id`: stable task identifier
- `params.start`: event collection start timestamp/date
- `params.end`: event collection end timestamp/date
- `params.events`: non-empty list of event overview rows

Optional task key fields:

- `params.focus_sectors`: focused sectors/themes
- `params.symbols`: focused symbols
- `output_root`: local receipt/request-manifest root

Each event row requires:

- `event_id` or enough fields for a deterministic generated id
- `event_time`
- `available_time` or defaults to `event_time`
- `information_role`: `lagging_evidence` or `prior_signal`
- `event_category`: `macro_data`, `macro_news`, `sector_news`, `symbol_news`, `sec_filing`, `option_abnormal_activity`, or `equity_abnormal_activity`
- `scope_type`: `macro`, `sector`, or `symbol`
- `title` or `headline`
- `source_name`
- `reference_type`: `web_url`, `sec_file_path`, `internal_artifact_path`, or `source_reference`
- `reference`

## Output

Final saved output is SQL-only:

```text
model_inputs.event_overlay_event
```

Natural key:

```text
event_id
```

Columns:

- `event_id`
- `event_time`
- `available_time`
- `information_role`
- `event_category`
- `scope_type`
- `symbol`
- `sector_type`
- `title`
- `summary`
- `source_name`
- `reference_type`
- `reference`

The table stores overview rows only. It does not store full article text, SEC filing contents, model impact scores, or trade recommendations.
