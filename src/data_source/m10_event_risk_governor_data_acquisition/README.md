# m10_event_risk_governor_data_acquisition

Manager-facing EventRiskGovernor data source.

Layer 10 supplies bounded, point-in-time event overview rows for the event-risk governor model. The output is one SQL table and one row per observed event/evidence row, with explicit canonical-event and deduplication fields so duplicate coverage does not become duplicate alpha. Full news text, SEC filing detail, macro-calendar payloads, abnormal-activity or price-action detector payloads, browser/agent analysis, and revision-specific artifacts stay behind references such as web URLs, SEC file paths, source references, or internal artifact paths.

This source is an event index, not the full `event_context_vector`. `EventRiskGovernor` combines these overview rows with point-in-time event artifacts, upstream `market_context_state` / `sector_context_state` / `target_context_state` references, and scope/sensitivity metadata inside `trading-model`.

Stable defaults live in pipeline code; there is no source-local `config.json`.

## Input parameters

Required task key fields:

- `source`: `m10_event_risk_governor_data_acquisition`
- `task_id`: stable task identifier
- `params.start`: event collection start timestamp/date
- `params.end`: event collection end timestamp/date
- `params.events`, `params.event_sql_inputs`, or `params.event_artifact_paths`: at least one explicit event overview row, SQL feed input, or reviewed local feed artifact path

Optional task key fields:

- `params.focus_sectors`: focused sectors/themes
- `params.symbols`: focused symbols
- `params.event_sql_inputs` / `params.feed_sql_inputs`: SQL feed rows to normalize into event overview rows. Supported current inputs are `feed_03_alpaca_news` (`symbol_news`), `feed_05_gdelt_article` (`macro_news` / `sector_news` / `symbol_news` by scope hints), `feed_12_release_calendar` (`earnings_guidance` scheduled shells for `nasdaq_earnings_calendar`), and `feed_08_sec_company_fact` (`earnings_guidance` result artifacts for 10-Q/10-K or earnings-related 8-K rows; otherwise `sec_filing`). Each entry may provide `table`, `kind`, `columns`, `where_equals`, `where_in`, `time_column`, `start`, `end`, and `order_by`.
- `params.event_artifact_paths` / `params.feed_artifact_paths`: compatibility/reviewed local artifact input. Use this for TE-exception or explicitly reviewed local evidence only, not for current non-TE feed outputs.
- Trading Economics macro rows stay in canonical storage and are not valid Layer 10 input until a later accepted route explicitly promotes them.
- `output_root`: local receipt/request-manifest root

Each event row requires:

- `event_id` or enough fields for a deterministic generated id. Generated ids use event category, event time, symbol, and reference; when those collide inside the same batch, source name plus title/headline are added as deterministic disambiguators so same-time calendar releases with different titles remain distinct rows.
- `event_time`
- `available_time` or defaults to `event_time`
- `information_role_type`: `lagging_evidence` or `prior_signal`
- `event_category_type`: `macro_data`, `macro_news`, `sector_news`, `symbol_news`, `sec_filing`, `earnings_guidance`, `option_abnormal_activity`, `equity_abnormal_activity`, or `price_action`. Here `macro_data` is an event category label, not an active executable feed. `earnings_guidance` rows must distinguish calendar-only scheduled shells from official result/guidance artifacts in `summary` / `coverage_reason`.
- `scope_type`: `macro`, `sector`, or `symbol`
- `title` or `headline`
- `source_name`
- `reference_type`: `web_url`, `sec_file_path`, `internal_artifact_path`, or `source_reference`
- `reference`
- `source_artifact_path`: optional local source artifact path when the event row was normalized from retained storage evidence

Optional deduplication fields:

- `canonical_event_id`: canonical event identity after deduplication; defaults to `event_id` for canonical rows
- `dedup_status`: one of `canonical`, `covered_by_canonical_event`, `duplicate_of_canonical_event`, `related_followup`, `new_information`, or `unresolved`; defaults to `canonical`
- `source_priority`: one of `official_disclosure`, `official_data_release`, `approved_calendar`, `company_disclosure`, `regulatory_disclosure`, `source_detector`, `verified_news`, `broad_news`, `derivative_news`, or `unknown`; inferred when omitted
- `coverage_reason`: short reason for canonical/covered/new-information status; full browser/agent analysis should stay in an artifact/report reference
- `covered_by_event_id`: canonical event id that covers this row; required for `covered_by_canonical_event` and `duplicate_of_canonical_event` rows unless supplied through `canonical_event_id`

Official SEC/exchange/company/regulatory disclosures outrank derivative news coverage. A news article that merely summarizes a represented SEC filing should be `dedup_status=covered_by_canonical_event`, with `canonical_event_id` pointing to the official filing event. It may contribute to attention/propagation context, but it must not create an independent alpha event/factor unless browser/agent analysis finds genuinely new information observable at its own `available_time`.

## Output

Final saved output is SQL-only:

```text
m10_event_risk_governor_data_acquisition
```

Natural key:

```text
event_id
```

Columns:

- `event_id`
- `canonical_event_id`
- `dedup_status`
- `source_priority`
- `coverage_reason`
- `covered_by_event_id`
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
- `source_artifact_path`

The table stores overview rows only. It does not store full article text, SEC filing contents, browser/agent analysis transcripts, event artifact payloads, model impact scores, labels, alpha confidence, or trade recommendations.

Feed-artifact extraction is local and offline only. It reads already-saved artifacts and never calls providers, dispatches manager requests, activates models, writes dashboard read models, or mutates broker/account state. Missing required event feed artifacts must block event-risk rebuild rather than allowing abnormal-activity-only outputs to stand as complete. Extracted feed rows are filtered to the requested `[params.start, params.end)` window before SQL persistence; out-of-window rows are skipped and reported in the clean-step warning/details so current-page artifacts cannot leak into historical rebuilds.

Trading Economics calendar artifacts have one accepted source role:

- canonical storage artifacts provide macro calendar/value evidence for reviewed historical windows.

TE original artifacts are retained as append-only source evidence in storage because they are not reliably recoverable later. SQL rows are derived materializations, not the TE source of truth, and should stay empty for TE macro rows until Layer 10 explicitly promotes macro events into the accepted event-risk/attention pool. The Trading Economics subscription is expired, so website URLs are not source references and no logged-out visible-page route is an accepted normal recovery path. Any non-TE fallback evidence must remain distinguishable by `source_name` / `coverage_reason` and must not be silently merged into TE-origin rows.

`price_action` rows are source-detector rows for price-behavior events such as `false_breakout`, `false_breakdown`, `liquidity_sweep_high`, `liquidity_sweep_low`, `bull_trap`, and `bear_trap`. The overview row keeps only the event/category/reference envelope; detector details stay behind the referenced artifact or nested detector output.

Additional columns such as `event_native_scope_type`, `declared_scope_type`, `industry_type`, `theme_tags`, revision ids, source update timestamps, or structured analysis-report links require explicit SQL migration plus registry review before use.
