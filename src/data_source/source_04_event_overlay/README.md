# source_04_event_overlay

Manager-facing EventOverlayModel data source.

Layer 04 supplies bounded, point-in-time event overview rows for the event overlay model. The output is one SQL table and one row per observed event/evidence row, with explicit canonical-event and deduplication fields so duplicate coverage does not become duplicate alpha. Full news text, SEC filing detail, macro-calendar payloads, abnormal-activity or price-action detector payloads, browser/agent analysis, and revision-specific artifacts stay behind references such as web URLs, SEC file paths, source references, or internal artifact paths.

This source is an event index, not the full `event_context_vector`. `EventOverlayModel` combines these overview rows with point-in-time event artifacts, upstream `market_context_state` / `sector_context_state` / `target_context_state` references, and scope/sensitivity metadata inside `trading-model`.

Stable defaults live in pipeline code; there is no source-local `config.json`.

## Input parameters

Required task key fields:

- `source`: `source_04_event_overlay`
- `task_id`: stable task identifier
- `params.start`: event collection start timestamp/date
- `params.end`: event collection end timestamp/date
- `params.events` or `params.event_artifact_paths`: at least one explicit event overview row or one reviewed local feed artifact path

Optional task key fields:

- `params.focus_sectors`: focused sectors/themes
- `params.symbols`: focused symbols
- `params.event_artifact_paths` / `params.feed_artifact_paths`: reviewed local saved artifacts to normalize into event overview rows. Supported artifacts are `03_feed_alpaca_news` `equity_news.csv` (`symbol_news`), `05_feed_gdelt_news` `gdelt_article.csv` (`macro_news` / `sector_news` / `symbol_news` by scope hints), `07_feed_trading_economics_calendar_web` `trading_economics_calendar_event.csv` (`macro_data`), and `08_feed_sec_company_financials` SEC CSV outputs (`sec_filing` / financial disclosure events).
- `output_root`: local receipt/request-manifest root

Each event row requires:

- `event_id` or enough fields for a deterministic generated id
- `event_time`
- `available_time` or defaults to `event_time`
- `information_role_type`: `lagging_evidence` or `prior_signal`
- `event_category_type`: `macro_data`, `macro_news`, `sector_news`, `symbol_news`, `sec_filing`, `option_abnormal_activity`, `equity_abnormal_activity`, or `price_action`. Here `macro_data` is an event category label, not an active executable feed.
- `scope_type`: `macro`, `sector`, or `symbol`
- `title` or `headline`
- `source_name`
- `reference_type`: `web_url`, `sec_file_path`, `internal_artifact_path`, or `source_reference`
- `reference`

Optional deduplication fields:

- `canonical_event_id`: canonical event identity after deduplication; defaults to `event_id` for canonical rows
- `dedup_status`: one of `canonical`, `covered_by_canonical_event`, `duplicate_of_canonical_event`, `related_followup`, `new_information`, or `unresolved`; defaults to `canonical`
- `source_priority`: one of `official_disclosure`, `official_data_release`, `company_disclosure`, `regulatory_disclosure`, `source_detector`, `verified_news`, `broad_news`, `derivative_news`, or `unknown`; inferred when omitted
- `coverage_reason`: short reason for canonical/covered/new-information status; full browser/agent analysis should stay in an artifact/report reference
- `covered_by_event_id`: canonical event id that covers this row; required for `covered_by_canonical_event` and `duplicate_of_canonical_event` rows unless supplied through `canonical_event_id`

Official SEC/exchange/company/regulatory disclosures outrank derivative news coverage. A news article that merely summarizes a represented SEC filing should be `dedup_status=covered_by_canonical_event`, with `canonical_event_id` pointing to the official filing event. It may contribute to attention/propagation context, but it must not create an independent alpha event/factor unless browser/agent analysis finds genuinely new information observable at its own `available_time`.

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

The table stores overview rows only. It does not store full article text, SEC filing contents, browser/agent analysis transcripts, event artifact payloads, model impact scores, labels, alpha confidence, or trade recommendations.

Feed-artifact extraction is local and offline only. It reads already-saved artifacts and never calls providers, dispatches manager requests, activates models, writes dashboard read models, or mutates broker/account state. Missing required event feed artifacts must block Layer 4+ rebuild rather than allowing abnormal-activity-only outputs to stand as complete.

`price_action` rows are source-detector rows for price-behavior events such as `false_breakout`, `false_breakdown`, `liquidity_sweep_high`, `liquidity_sweep_low`, `bull_trap`, and `bear_trap`. The overview row keeps only the event/category/reference envelope; detector details stay behind the referenced artifact or nested detector output.

Additional columns such as `event_native_scope_type`, `declared_scope_type`, `industry_type`, `theme_tags`, revision ids, source update timestamps, or structured analysis-report links require explicit SQL migration plus registry review before use.
