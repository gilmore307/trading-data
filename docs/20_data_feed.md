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
| Trading Economics calendar web | Recent/future macro calendar rows plus retained monthly source snapshots. | bounded TE calendar-page fetch into canonical `trading-storage` source data | Accepted macro source evidence is storage-owned TE rows. Source artifacts must not carry TE website URLs and must not populate Layer 10 SQL rows without a later reviewed route. |
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
| Trading Economics calendar web | `trading-data-07-feed-trading-economics-calendar-web` / `python -m data_feed.07_feed_trading_economics_calendar_web` | bounded recent/future calendar acquisition and parser for reviewed HTML inputs |
| SEC company financials | `trading-data-08-feed-sec-company-financials` / `python -m data_feed.08_feed_sec_company_financials` | cleaned SEC company facts/submission evidence |
| ThetaData option selection snapshot | `trading-data-09-feed-thetadata-option-selection-snapshot` / `python -m data_feed.09_feed_thetadata_option_selection_snapshot` | final option-chain snapshot artifact |
| ThetaData option primary tracking | `trading-data-10-feed-thetadata-option-primary-tracking` / `python -m data_feed.10_feed_thetadata_option_primary_tracking` | final `option_bar.csv` for a supplied contract |
| ThetaData option event timeline | `trading-data-11-feed-thetadata-option-event-timeline` / `python -m data_feed.11_feed_thetadata_option_event_timeline` | event CSV plus compact per-event detail JSON |
| Official calendar discovery | `trading-data-12-feed-official-calendar-discovery` / `python -m data_feed.12_feed_official_calendar_discovery` | official calendar artifacts for `calendar_observation` |

## Browser-Scraped Web Feeds

Browser-scraped provider routes use bounded visible-page requests:

- prefer logged-out public pages when they provide the accepted fields;
- pass task-specific date/filter cookies or query params through ordinary HTTP requests;
- do not start a new browser or log in for every data task;
- do not make normal data acquisition depend on mutating a long-lived page/tab state;
- use an authenticated browser profile or exported cookie jar only for a reviewed manual recovery route that explicitly requires it;
- if captcha, MFA, permission prompts, or WAF blocks appear, stop and require operator action instead of bypassing them;
- parser output must be filtered to the requested time/window and record skipped out-of-window rows in receipt warnings/details.

Trading Economics recent/future calendar acquisition is active as a bounded calendar-page route. The active macro source is still the canonical storage data owned by `trading-storage`:

```text
storage/01_source_data/monthly_backfill/trading_economics_calendar_web
```

The feed package may fetch the bounded recent/future calendar window or parse reviewed HTML inputs. It must not write website URLs into source artifacts, call TE API/download/export endpoints, or materialize Layer 10 SQL event rows.

## Trading Economics Recent Refresh

Trading Economics calendar rows are reusable source data only after they are saved into the canonical storage source tree:

```text
storage/01_source_data/monthly_backfill/trading_economics_calendar_web
```

The recent/future refresh wrapper is:

```bash
PYTHONPATH=src python3 scripts/data/run_trading_economics_recent_calendar_refresh.py
```

Without `--execute-live-fetch` it returns a plan-only receipt. With `--execute-live-fetch` it performs one bounded calendar-page request and appends rows into monthly storage buckets without persisting website URL fields. The checked-in systemd timer may schedule this refresh; it is not a Layer 10 event-admission route.

The visible calendar request pins the page timezone to `America/New_York`; saved `event_time` values are New York local macro-release times with explicit offsets.

## Calendar Observations

`calendar_observation` is the unified source-shell layer for scheduled calendar facts. It can be built from accepted inputs such as deterministic market-session rows, deterministic option-expiry/OPEX windows, official exchange calendar artifacts, headline index methodology/announcement artifacts, Trading Economics macro calendar rows, and `calendar_discovery` `release_calendar.csv` artifacts including Nasdaq earnings calendar rows.

The builder is:

```bash
PYTHONPATH=src python3 scripts/data/build_calendar_observations.py --start-date 2026-06-01 --end-date 2026-07-01 --include-market-sessions --include-option-expiry --include-headline-index-calendar --output-dir <output>
```

Output files:

- `calendar_observation.csv`
- `calendar_observation.jsonl`
- `schema.json`

Calendar observations are not Layer 10 event-pool rows. They preserve scheduling clocks, source priority, lifecycle class, certainty, and payload refs so Layer 10 can later promote only relevant observations into focused event acquisition or attribution. Nasdaq earnings-calendar rows remain tentative `earnings_calendar` shells with `result_fields_not_available`; Trading Economics rows remain macro calendar/value source observations; option-expiry and market-session rows are rule-backed market-structure observations until official sources or Layer 10 promotion add stronger evidence.

Optional artifact inputs are `--official-exchange-calendar`, `--index-calendar`, `--release-calendar`, and `--trading-economics-calendar`. Exchange-calendar artifacts preserve official holiday and early-close rows; index-calendar artifacts preserve official methodology or announcement rows. Index-calendar expansion is limited to Nasdaq-100, S&P 500, and Dow Jones Industrial Average. Nasdaq-100 may use Nasdaq Global Indexes methodology calendars for scheduled shells and Nasdaq announcements for membership results. S&P 500 may use S&P DJI methodology/index facts for quarterly maintenance windows and S&P DJI announcements for additions/deletions. DJIA has no fixed constituent-reconstitution schedule, so only S&P DJI announcement artifacts should create constituent-change observations. ETF issuer pages are outside this source route.

`12_feed_official_calendar_discovery` is the feed-level entrypoint for official or reviewed calendar artifacts:

- Nasdaq earnings calendar rows become tentative `release_calendar.csv` shells;
- Nasdaq Global Indexes and S&P DJI announcement rows become `index_calendar.csv`;
- NYSE/Nasdaq official holiday and early-close rows become `official_exchange_calendar.csv`.

These artifacts remain source-shell inputs. Scheduler registration and Layer 10 promotion are separate manager/model decisions.

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

`macro_data` is not an active feed. Macro model-input rows use the canonical Trading Economics storage snapshot when a reviewed route materializes macro rows. Official macro API aliases may remain for reviewed research, but manager-issued macro tasks must not use the expired TE website route.

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
