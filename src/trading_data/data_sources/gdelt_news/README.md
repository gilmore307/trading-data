# gdelt_news bundle

`gdelt_news` acquires global source article evidence from GDELT BigQuery. It is the primary broad news source for political, economic, technology, geopolitical, sector, and broad-market event discovery.

Run:

```bash
PYTHONPATH=src:/root/projects/trading-main/src python3 -m trading_data.data_sources.gdelt_news task.json --run-id gdelt_news_run_<id>
```

Required params:

- `query_terms` — string or list of strings searched against GDELT GKG URL/theme/name/entity fields.

Optional params:

- `start_date`, `end_date` — `YYYY-MM-DD` partition date bounds.
- `lookback_days` — used when `start_date` is omitted; defaults to `1`.
- `max_rows` — 1 to 1000; defaults to `100`.
- `search_fields` — `themes_text`, `url_only`, or `all_text`; defaults to `themes_text`.
- `impact_scope_hint` — default hint for event extraction, defaults to `market;sector;industry;theme`.

Outputs:

- `request_manifest.json` — query metadata and sanitized SQL evidence.
- `cleaned/gdelt_article.jsonl` and `cleaned/schema.json` — run-local normalized rows.
- `saved/gdelt_article.csv` — final source evidence rows.
- `completion_receipt.json` — per-run status and outputs.

Boundary:

- This bundle saves GDELT article/source evidence, not final canonical events.
- Later event extraction/clustering projects `gdelt_article` into `trading_event` / `event_factor`.
- SEC/company official disclosures still outrank derivative news coverage for canonical event identity.
