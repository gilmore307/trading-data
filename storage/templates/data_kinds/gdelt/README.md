# GDELT data kind templates

GDELT is the primary broad news/event discovery source for U.S. and U.S.-market political, economic, technology, geopolitical, sector, industry, theme, and market-impact event candidates.

## `gdelt_article`

- **Source:** GDELT BigQuery public dataset via the service-account alias `gdelt`.
- **Bundle:** `gdelt_news`.
- **Status:** `implemented`.
- **Persistence policy:** Persist compact source-evidence article rows. Do not persist full raw BigQuery responses by default.
- **Earliest available range:** source/table-specific; the current bundle queries `gdelt-bq.gdeltv2.gkg_partitioned` by partition date.
- **Default timestamp semantics:** `seen_at_utc` is UTC because it is a source observation time; event projection should add `event_time_et` / `effective_time_et` when creating `trading_event` rows.
- **Natural grain:** One GDELT GKG article/source-evidence record.
- **Request parameters:** `query_terms`, optional `start_date`, `end_date`, `lookback_days`, `max_rows`, `search_fields`, `focus`, `source_domain_allowlist`, `source_domain_contains`, `impact_scope_hint`.
- **Pagination/range behavior:** Bound by date partition, `max_rows`, and default `focus=us_market`; wider history should be segmented by date/theme/query.
- **Preview file:** see `gdelt_article.preview.csv`.
- **Known caveats:** This is source evidence, not canonical event identity. SEC/company official disclosures still outrank derivative news. Downstream event clustering must merge related GDELT articles with official/source-of-truth events and avoid duplicate alpha counting. The default bundle behavior intentionally does not acquire all global GDELT rows; it pre-filters for U.S./U.S.-market relevance in BigQuery.
