# 07_feed_trading_economics_calendar_web feed

`07_feed_trading_economics_calendar_web` is a conservative web-page interface for Trading Economics calendar rows. It is intended to enrich macro-release events with visible page fields such as Actual, Previous, Consensus, and Forecast.

Boundary:

- Use visible website calendar data only; current/recent and custom-date routes do not require a logged-in session by default.
- Do not call Trading Economics API endpoints or Download/export features.
- Do not bypass WAF/captcha/permissions.
- Historical custom-window live fetches use a request-specific custom date-range cookie, then parse the returned calendar page rows. The current accepted route is logged-out visible-page fetch.
- Realtime recent fetches use `date_range_mode=recent` and `use_authenticated_cookies=false`; this reads the logged-out recent visible calendar page and filters rows to the task window.
- Operational historical acquisition order is logged-out visible-page HTTP first for efficiency; if it fails, retry once after 60 seconds; if the retry also fails, use the reviewed real browser UI route (`Custom` From/Until, `Submit`, captured rendered page parsed through `html_path`) as a narrow fallback.
- Keep runs bounded; bulk backfills require reviewed source and storage parameters.
- Saved rows are filtered to `[start_date, end_date)`; server-inclusive end-date rows are skipped and reported in receipt warnings/details.

Run:

```bash
PYTHONPATH=src:${TRADING_MANAGER_SRC:-../trading-manager/src} python3 -m data_feed.07_feed_trading_economics_calendar_web task.json --run-id te_calendar_run_<id>
```

Params:

- `start_date`, `end_date` — one bounded calendar window, normally one month or smaller.
- `country` — defaults to `United States`.
- `importance` — defaults to `3` for high-impact rows.
- `html_path` — optional captured/sanitized HTML for parser tests or manual page captures.
- `html` — optional inline sanitized HTML.
- `allow_live_fetch` — optional; when true, fetches the visible page.
- `date_range_mode` — optional; `custom` by default for bounded historical windows, or `recent` for the logged-out recent calendar page.
- `use_authenticated_cookies` — optional; defaults to false. Set true only for a reviewed manual recovery route that explicitly needs an exported local cookie jar.
- `persist_failure_diagnostics` — optional; when true and parsing finds zero in-window rows, writes sanitized structural diagnostics under the run directory. It does not persist request headers, cookies, or raw page HTML.

Outputs:

- `request_manifest.json`
- `cleaned/trading_economics_calendar_event.jsonl`
- `saved/trading_economics_calendar_event.csv`
- `completion_receipt.json`
- `diagnostics/te_calendar_failure_diagnostic.json` — optional failure-only sanitized structure/excerpt report when `persist_failure_diagnostics=true`
