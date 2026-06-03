# 12_feed_official_calendar_discovery

Official calendar-discovery feed for scheduled or announced event shells.

This feed writes source artifacts that `calendar_observation` can consume. It does not admit rows into the Layer 10 event pool.

Supported `params.data_kind` values:

- `nasdaq_earnings_calendar` -> `saved/release_calendar.csv`
- `official_index_announcement` -> `saved/index_calendar.csv`
- `official_exchange_calendar` -> `saved/official_exchange_calendar.csv`

Live requests require manager provider controls. Fixture or reviewed local artifact inputs may use `json_path`, `json_text`, `csv_path`, `text_path`, or `source_text`.

Rules:

- Nasdaq earnings calendar rows are tentative discovery shells; SEC/company official artifacts outrank them for results and guidance.
- Index announcements are limited to Nasdaq Global Indexes and S&P Dow Jones Indices for `NDX`, `SPX`, and `DJIA`.
- ETF issuer pages are not accepted for index-calendar announcement rows.
- Exchange calendar rows preserve official holiday and early-close evidence only.

