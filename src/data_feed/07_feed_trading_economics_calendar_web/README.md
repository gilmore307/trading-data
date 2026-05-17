# 07_feed_trading_economics_calendar_web feed

`07_feed_trading_economics_calendar_web` is a conservative web-page interface for Trading Economics calendar rows. It is intended to enrich macro-release events with visible page fields such as Actual, Previous, Consensus, and Forecast.

Boundary:

- Use logged-in visible website calendar data only.
- Do not call Trading Economics API endpoints or Download/export features.
- Do not bypass WAF/captcha/permissions.
- Live fetches use the local authenticated cookie jar plus a request-specific custom date-range cookie, then parse the returned calendar page rows.
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
- `allow_live_fetch` — optional; when true, fetches the visible page with normal authenticated HTTP cookies if available and overlays the requested custom date-range cookie.

Outputs:

- `request_manifest.json`
- `cleaned/trading_economics_calendar_event.jsonl`
- `saved/trading_economics_calendar_event.csv`
- `completion_receipt.json`
