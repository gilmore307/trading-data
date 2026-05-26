# Data Feed

`data_feed` is the provider/source access layer. It talks to one provider/API/web/file family, normalizes feed-level evidence, and stays below manager-facing model-input orchestration.

## Feed Boundary

A feed owns:

- provider/client setup;
- authentication by secret alias or documented no-key rule;
- request construction;
- pagination, timeout, retry, and rate-limit behavior;
- provider-specific errors and entitlement evidence;
- timestamp normalization;
- final cleaned feed outputs or transient rows for a source;
- fixture-safe default tests.

A feed does not own model labels, strategy signals, execution decisions, dashboard presentation, durable storage policy, or secret values.

## Package Layout

```text
src/
  data_feed/         Provider/API/web/file feed implementations.
  feed_interfaces/   Provider/data-kind catalog and bounded smoke interfaces.
  data_source/       Manager-facing source orchestration.
  data_feature/      Deterministic feature construction from accepted source outputs.
  storage/           Low-level persistence helpers.
  feed_availability/ Documentation/probe inventory support.
```

Shared helpers and reusable names belong in `trading-manager`, not in local ad hoc folders.

## Credentials

Provider credentials must never be committed. Secret material stays outside Git under `/root/secrets/<alias>.json`; repository code and docs may reference only approved aliases.

| Provider/source | Role | Alias/config | Notes |
|---|---|---|---|
| Alpaca | Stock/ETF bars, trades, quotes, snapshots, news. | `ALPACA_SECRET_ALIAS` -> `alpaca` | Endpoint and secret values stay in `/root/secrets/alpaca.json`. |
| ThetaData | Option contracts, snapshots, OHLC, trade/quote, open interest, IV, Greeks. | `THETADATA_SECRET_ALIAS` -> `thetadata` | Local Terminal v3 runs outside the repo and serves `127.0.0.1:25503` when started. |
| OKX | Crypto market data; private surfaces only when separately approved. | `OKX_SECRET_ALIAS` -> `okx` | Public market data may not need private credentials. |
| SEC EDGAR | Company submissions, facts, concepts, frames, filing metadata. | no key | Requires fair-access behavior and identifying User-Agent. |
| ETF issuers | Holdings rows, weights, fund metadata. | issuer-specific/no key | Preserve source URL, as-of date, retrieval time, and file/page format. |
| Trading Economics visible calendar | Macro calendar/value rows visible on the public recent/custom calendar pages. | no key; no authenticated cookies by default | Accepted runtime authority for macro event observations because the row shape includes scheduled time plus expectation/previous/actual-style fields when visible. Feed tasks use logged-out visible-page requests with bounded date/filter cookies. No API/download/WAF/captcha bypass. |
| FRED/Census/BEA/BLS/Treasury | Optional official macro/economic research surfaces. | aliases where registered | Not active manager macro routes; use only for incident review, audit, or a separately accepted replacement route. |
| FOMC/official release pages | Official calendar events. | no key | Not an active macro runtime route while TE is accepted; preserve as manual fallback/audit source. |

Provider term rows, data-kind rows, config aliases, and shared metadata are owned by `trading-manager`.

## Active Feed CLIs

Installed entrypoints mirror package modules:

| Feed | Command/module | Output stance |
|---|---|---|
| Alpaca bars | `trading-data-01-feed-alpaca-bars` / `python -m data_feed.01_feed_alpaca_bars` | final `equity_bar` CSV; no raw payload persistence by default |
| Alpaca liquidity | `trading-data-02-feed-alpaca-liquidity` / `python -m data_feed.02_feed_alpaca_liquidity` | ET-aligned `equity_liquidity_bar`; raw trades/quotes are transient |
| Alpaca news | `trading-data-03-feed-alpaca-news` / `python -m data_feed.03_feed_alpaca_news` | final `equity_news` CSV |
| OKX crypto market data | `trading-data-04-feed-okx-crypto-market-data` / `python -m data_feed.04_feed_okx_crypto_market_data` | cleaned crypto market outputs |
| GDELT news | `trading-data-05-feed-gdelt-news` / `python -m data_feed.05_feed_gdelt_news` | bounded news evidence |
| ETF holdings | `trading-data-06-feed-etf-holdings` / `python -m data_feed.06_feed_etf_holdings` | issuer holdings evidence |
| Trading Economics calendar web | `trading-data-07-feed-trading-economics-calendar-web` / `python -m data_feed.07_feed_trading_economics_calendar_web` | visible calendar/value rows |
| SEC company financials | `trading-data-08-feed-sec-company-financials` / `python -m data_feed.08_feed_sec_company_financials` | cleaned SEC company facts/submission evidence |
| ThetaData option selection snapshot | `trading-data-09-feed-thetadata-option-selection-snapshot` / `python -m data_feed.09_feed_thetadata_option_selection_snapshot` | final option-chain snapshot artifact |
| ThetaData option primary tracking | `trading-data-10-feed-thetadata-option-primary-tracking` / `python -m data_feed.10_feed_thetadata_option_primary_tracking` | final `option_bar.csv` for a supplied contract |
| ThetaData option event timeline | `trading-data-11-feed-thetadata-option-event-timeline` / `python -m data_feed.11_feed_thetadata_option_event_timeline` | event CSV plus compact per-event detail JSON |

## Browser-Scraped Web Feeds

Browser-scraped provider routes use bounded visible-page requests:

- prefer logged-out public pages when they provide the accepted fields;
- pass task-specific date/filter cookies or query params through ordinary HTTP requests;
- do not start a new browser or log in for every data task;
- do not make normal data acquisition depend on mutating a long-lived page/tab state;
- use an authenticated browser profile or exported cookie jar only for a reviewed manual recovery route that explicitly requires it;
- if captcha, MFA, permission prompts, or WAF blocks appear, stop and require operator action instead of bypassing them;
- parser output must be filtered to the requested time/window and record skipped out-of-window rows in receipt warnings/details.

Trading Economics uses logged-out visible-page requests for replay windows, recent rows, and future scheduled releases. Ongoing maintenance fetches bounded current/recent/future calendar rows and keeps parser output filtered to the requested window.

## Trading Economics Recent Refresh

Trading Economics calendar rows are reusable event/source data. Historical monthly backfill lives under:

```text
storage/01_source_data/monthly_backfill/trading_economics_calendar_web
```

Continuous recent refresh fetches one bounded rolling window, then appends the parsed rows into the same month-bucketed historical root by `event_time` month:

```text
storage/01_source_data/monthly_backfill/trading_economics_calendar_web/YYYY-MM/runs/<run_id>
```

The wrapper is:

```bash
PYTHONPATH=src python3 scripts/data/run_trading_economics_recent_calendar_refresh.py
```

Default behavior is plan-only and performs no provider calls. Add `--execute-live-fetch` only for the bounded visible-page recent calendar fetch. The checked-in systemd timer is:

```text
deploy/systemd/trading-data-te-calendar-refresh.timer
```

It runs one visible-page request per cycle with a 7-day trailing and 35-day forward window, `date_range_mode=recent`, no authenticated cookies, and manager-controls set for provider maintenance. Because the recent window can cross month boundaries, the feed writes month-specific CSV/JSONL copies under each affected `YYYY-MM` directory and keeps the run-wide control receipt under the TE monthly root. Existing historical TE artifacts remain append-only and are not deletion candidates.

## Implementation Rules

- A feed starts as one `pipeline.py` with clear fetch/clean/save/receipt steps; split only when complexity demands it.
- Feed code may write storage-owned development evidence under `trading-storage/storage/01_source_data/`, but source/model-facing accepted outputs should be SQL or explicitly reviewed artifacts.
- High-volume raw rows are transient by default. Persist aggregates or final cleaned outputs unless an approved debug/incident artifact says otherwise.
- Default tests must not require live credentials or network calls.
- Live calls require explicit guardrails: bounded symbols/contracts, bounded windows, request/row caps, timeouts, retry policy, secret aliases, and sanitized evidence.

## ThetaData Runtime

ThetaData option feeds require the local Theta Terminal v3 runtime outside the repository:

```text
/root/tools/thetadata-terminal/ThetaTerminalv3.jar
http://127.0.0.1:25503/v3
```

Credential material is generated from `/root/secrets/thetadata.json` into local runtime files and must never be committed or printed. The connector is integrated and has passed a controlled smoke through `10_feed_thetadata_option_primary_tracking`; a closed port means the runtime is not started, not that the feed is unimplemented.

## Macro Route

`macro_data` is not an active feed. Macro model-input rows currently use `07_feed_trading_economics_calendar_web` visible-page evidence. Official macro API aliases may remain for reviewed research, but manager-issued macro tasks must use an accepted active route.

## Acceptance Checklist

A feed is acceptable when:

- no secret values are stored or logged;
- credentials are alias-only;
- provider/source capabilities and limits are documented;
- tests are fixture-safe by default;
- retry/rate-limit behavior is bounded;
- timestamps and timezones are explicit;
- final outputs are minimal, reviewed, and reproducible;
- reusable names are registered through `trading-manager`.
