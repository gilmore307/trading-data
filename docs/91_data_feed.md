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
| Trading Economics visible calendar | Macro calendar/value rows visible on logged-in pages. | authenticated browser-session cookie jar; no API key for accepted route | Session/cookie helper maintains login; feed tasks consume cookies. No API/download/WAF/captcha bypass. |
| FRED/Census/BEA/BLS/Treasury | Optional official macro/economic research surfaces. | aliases where registered | Not active manager macro routes unless separately accepted. |
| FOMC/official release pages | Official calendar events. | no key | Use official source pages and preserve retrieval metadata. |

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

Browser-scraped provider routes use the shared session-cookie pattern:

- keep one authenticated browser profile/session for login, consent, and cookie refresh;
- export provider cookies to local secret storage such as `/root/secrets/<provider>-cookies.txt`;
- normal feed tasks fetch provider pages through bounded HTTP requests that consume the cookie jar and task-specific date/filter cookies or query params;
- do not start a new browser or log in for every data task;
- do not make normal data acquisition depend on mutating a long-lived page/tab state;
- when cookies expire, refresh the authenticated profile/session first, then rerun the feed task;
- if captcha, MFA, permission prompts, or WAF blocks appear, stop and require operator action instead of bypassing them;
- parser output must be filtered to the requested time/window and record skipped out-of-window rows in receipt warnings/details.

This policy applies to Trading Economics and any future browser-scraped source accepted into `data_feed`.

## Implementation Rules

- A feed starts as one `pipeline.py` with clear fetch/clean/save/receipt steps; split only when complexity demands it.
- Feed code may write local ignored development evidence, but source/model-facing accepted outputs should be SQL or explicitly reviewed artifacts.
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
