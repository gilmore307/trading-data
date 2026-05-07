# source_04_event_overlay

Manager-facing EventOverlayModel data source.

Layer 04 supplies bounded, point-in-time event overview rows for the event overlay model. The output is one SQL table and one row per event. Full news text, SEC filing detail, macro-calendar payloads, abnormal-activity detector payloads, and revision-specific artifacts stay behind references such as web URLs, SEC file paths, source references, or internal artifact paths.

This source is an event index, not the full `event_context_vector`. `EventOverlayModel` combines these overview rows with point-in-time event artifacts, upstream `market_context_state` / `sector_context_state` / `target_context_state` references, and scope/sensitivity metadata inside `trading-model`.

Stable defaults live in pipeline code; there is no source-local `config.json`.

## Input parameters

Required task key fields:

- `source`: `source_04_event_overlay`
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
- `information_role_type`: `lagging_evidence` or `prior_signal`
- `event_category_type`: `macro_data`, `macro_news`, `sector_news`, `symbol_news`, `sec_filing`, `option_abnormal_activity`, or `equity_abnormal_activity`
- `scope_type`: `macro`, `sector`, or `symbol`
- `title` or `headline`
- `source_name`
- `reference_type`: `web_url`, `sec_file_path`, `internal_artifact_path`, or `source_reference`
- `reference`

## Output

Final saved output is SQL-only:

```text
source_04_event_overlay
```

Natural key:

```text
event_id
```

Columns:

- `event_id`
- `event_time`
- `available_time`
- `information_role_type`
- `event_category_type`
- `scope_type`
- `symbol`
- `sector_type`
- `title`
- `summary`
- `source_name`
- `reference_type`
- `reference`

The table stores overview rows only. It does not store full article text, SEC filing contents, event artifact payloads, model impact scores, labels, alpha confidence, or trade recommendations.

Future fields such as `event_native_scope_type`, `declared_scope_type`, `industry_type`, `theme_tags`, revision ids, and source update timestamps require explicit SQL migration plus registry review before they become active table columns.
