# gdelt_news bundle

`gdelt_news` acquires pre-filtered source article evidence from GDELT BigQuery. It is the primary broad news source for U.S. and U.S.-market political, economic, war/geopolitical, and technology event discovery.

Run:

```bash
PYTHONPATH=src:/root/projects/trading-main/src python3 -m trading_data.data_sources.gdelt_news task.json --run-id gdelt_news_run_<id>
```

Required params:

- None. If `query_terms` is omitted, the bundle defaults to the core market-impact topic categories below.

Optional params:

- `start_date`, `end_date` — `YYYY-MM-DD` partition date bounds.
- `lookback_days` — used when `start_date` is omitted; defaults to `1`.
- `max_rows` — 1 to 1000; defaults to `100`.
- `query_terms` — optional string or list of strings searched against GDELT GKG URL/theme/name/entity fields; overrides default category terms when supplied.
- `topic_categories` — defaults to `politics,economy,war,technology`; supported values are `politics`, `economy`, `war`, and `technology`.
- `search_fields` — `themes_text`, `url_only`, or `all_text`; defaults to `themes_text`.
- `focus` — defaults to `us_market`; use `none` only for explicit broader research.
- `source_domain_allowlist` — optional string/list of domains; defaults to a curated U.S./U.S.-market news-domain allowlist used together with U.S. location and U.S.-market text filters.
- `source_domain_contains` — optional extra domain substring filter.
- `impact_scope_hint` — default hint for event extraction, defaults to `market;sector;industry;theme`.

Outputs:

- `request_manifest.json` — query metadata and sanitized SQL evidence.
- `cleaned/gdelt_article.jsonl` and `cleaned/schema.json` — run-local normalized rows.
- `saved/gdelt_article.csv` — final source evidence rows.
- `completion_receipt.json` — per-run status and outputs.

Boundary:

- This bundle pre-filters at the BigQuery query layer; do not fetch global all-news rows and filter them locally by default.
- This bundle saves GDELT article/source evidence, not final canonical events.
- Later event extraction/clustering projects `gdelt_article` into `trading_event` / `event_factor`.
- SEC/company official disclosures still outrank derivative news coverage for canonical event identity.
