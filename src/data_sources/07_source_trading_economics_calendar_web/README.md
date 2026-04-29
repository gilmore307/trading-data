# 07_source_trading_economics_calendar_web bundle

`07_source_trading_economics_calendar_web` is a conservative web-page interface for Trading Economics calendar rows. It is intended to enrich macro-release events with visible page fields such as Actual, Previous, Consensus, and Forecast.

Boundary:

- Use visible website calendar data only.
- Do not call Trading Economics API endpoints or Download/export features.
- Do not bypass WAF/captcha/permissions.
- First version is an interface/parser scaffold; do not bulk backfill history yet.

Run:

```bash
PYTHONPATH=src:/root/projects/trading-main/src python3 -m data_sources.07_source_trading_economics_calendar_web task.json --run-id te_calendar_run_<id>
```

Params:

- `start_date`, `end_date` — one bounded calendar window, normally one month or smaller.
- `country` — defaults to `United States`.
- `importance` — defaults to `3` for high-impact rows.
- `html_path` — optional captured/sanitized HTML for parser tests or manual page captures.
- `html` — optional inline sanitized HTML.
- `allow_live_fetch` — optional; when true, fetches the visible page with normal HTTP cookies if available.

Outputs:

- `request_manifest.json`
- `cleaned/trading_economics_calendar_event.jsonl`
- `saved/trading_economics_calendar_event.csv`
- `completion_receipt.json`
