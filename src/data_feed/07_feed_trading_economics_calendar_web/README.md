# 07_feed_trading_economics_calendar_web feed

`07_feed_trading_economics_calendar_web` is the historical parser for Trading Economics calendar rows. The active macro source is now the canonical storage snapshot; the Trading Economics subscription is expired and the website is not an active provider source.

Boundary:

- Use canonical storage TE source data for active macro inputs.
- Do not use the Trading Economics website as an active source while the subscription is expired.
- Do not call Trading Economics API endpoints or Download/export features.
- Do not bypass WAF/captcha/permissions.
- `html_path`/`html` are parser-test and reviewed manual-capture inputs, not the normal provider acquisition path.
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
- `date_range_mode` — optional parser compatibility field; `custom` by default for bounded historical windows, or `recent` for the retired recent-calendar shape.
- `use_authenticated_cookies` — optional; defaults to false. Set true only for a reviewed manual recovery route that explicitly needs an exported local cookie jar.
- `persist_failure_diagnostics` — optional; when true and parsing finds zero in-window rows, writes sanitized structural diagnostics under the run directory. It does not persist request headers, cookies, or raw page HTML.

Outputs:

- `request_manifest.json`
- `cleaned/trading_economics_calendar_event.jsonl`
- `saved/trading_economics_calendar_event.csv`
- `completion_receipt.json`
- `diagnostics/te_calendar_failure_diagnostic.json` — optional failure-only sanitized structure/excerpt report when `persist_failure_diagnostics=true`
