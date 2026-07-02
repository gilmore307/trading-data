# 07_feed_trading_economics_calendar_web feed

`07_feed_trading_economics_calendar_web` is the bounded Trading Economics calendar-page feed for recent/future macro schedule maintenance plus reviewed HTML parsing.

Boundary:

- Save accepted TE rows only as canonical storage source data.
- Use bounded calendar-page fetches only for recent/future schedule maintenance.
- Do not call Trading Economics API endpoints or Download/export features.
- Do not bypass WAF/captcha/permissions.
- `html_path`/`html` are parser-test and reviewed manual-capture inputs.
- Do not persist website URLs as source evidence.
- Do not directly populate M06 SQL event rows from this feed; M06 materialization consumes reviewed storage artifacts.
- Keep runs bounded; bulk backfills require reviewed source and storage parameters.
- Saved rows are filtered to `[start_date, end_date)`; server-inclusive end-date rows are skipped and reported in receipt warnings/details.
- Request the visible calendar page with the `America/New_York` timezone offset; saved `event_time` values are New York local macro-release times with explicit offsets.
- Recent/future scheduled maintenance task keys use the local authenticated Trading Economics cookie jar by default. Historical/custom task keys keep `use_authenticated_cookies=false` unless a reviewed caller opts in.
- Save-step details include field coverage for `Actual`, `Previous`, `Consensus`, and `Forecast` so scheduled receipts can detect missing macro expectation baseline fields.

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
- `date_range_mode` — optional parser compatibility field; `custom` by default for bounded historical windows, or `recent` for recent/future refreshes.
- `allow_live_fetch` — optional; required for the bounded TE calendar-page request. Plan-only task keys leave this false.
- `use_authenticated_cookies` — optional; defaults to false at the feed level. The scheduled recent/future maintenance wrapper sets it true by default because unauthenticated TE pages may omit consensus/forecast cells.
- `persist_failure_diagnostics` — optional; when true and parsing finds zero in-window rows, writes sanitized structural diagnostics under the run directory. It does not persist request headers, cookies, or raw page HTML.

Outputs:

- `request_manifest.json`
- `cleaned/trading_economics_calendar_event.jsonl`
- `saved/trading_economics_calendar_event.csv`
- `completion_receipt.json`
- `diagnostics/te_calendar_failure_diagnostic.json` — optional failure-only sanitized structure/excerpt report when `persist_failure_diagnostics=true`
