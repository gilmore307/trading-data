# Temporal Explorer

`Temporal Explorer` is the shared calendar/timewheel substrate. Its purpose is to align time, market sessions, replay/model state, and compact visualization bars on the same inspectable timeline.

## SQL Substrate

| Table | Role |
|---|---|
| `trading_data.calendar_day` | Daily spine from the accepted historical start, one row per date. |
| `trading_data.calendar_market_session` | Venue session state for NYSE, NASDAQ, and `CRYPTO_24_7`. |
| `trading_data.chart_ohlcv_cache` | Compact visualization OHLCV cache for dashboard charts. |

## Calendar Observation Surface

`calendar_observation` is the source-shell artifact layer for scheduled calendar facts before M06 event-pool promotion. It is built from accepted calendar inputs such as rule-generated market sessions, deterministic option-expiry windows, Trading Economics macro calendar rows, and SQL-retained calendar-discovery rows.

Current implemented observation sources:

- `market_session` from deterministic NYSE/NASDAQ/crypto session rows;
- `weekly_option_expiry`, `monthly_option_expiry`, and `triple_witching` from deterministic Friday/third-Friday rules;
- official NYSE/NASDAQ holiday, closure, and early-close rows from accepted official exchange calendar rows;
- Nasdaq-100 and S&P 500 methodology-backed index schedule shells from the accepted headline-index route;
- official Nasdaq/S&P DJI index announcement rows from accepted `index_calendar` rows;
- `macro_release_calendar` from retained Trading Economics calendar rows;
- `earnings_calendar` and generic `release_calendar` from calendar-discovery rows, including Nasdaq earnings-calendar scheduled shells.

Accepted future index-calendar source routing:

- Nasdaq-100 scheduled annual reconstitution and quarterly rebalance shells may be derived from Nasdaq Global Indexes methodology calendars; actual membership changes need Nasdaq official announcement artifacts.
- S&P 500 quarterly maintenance/rebalance windows may be derived from S&P DJI methodology/index facts; actual additions and deletions need S&P DJI announcement artifacts.
- Dow Jones Industrial Average constituent changes must not be synthesized from a fixed schedule because the headline index changes as needed; use S&P DJI announcement artifacts with their visible effective dates.
- ETF issuer pages are outside the index-calendar source route.

Current non-goals:

- do not infer official early closes without an accepted official exchange source;
- do not synthesize company-action rows, index rebalance result rows, or corporate-action rows without accepted source artifacts;
- do not synthesize Dow Jones Industrial Average fixed reconstitution windows;
- do not insert calendar observations directly into M06 event tables.

## Timewheel Contract

The dashboard Timewheel should consume this substrate through storage read models. It presents:

- primary chart viewport centered on the selected time;
- selectable frames: `30m`, `1h`, `1D`, `1W`;
- chart x-axis used as the Timewheel axis;
- lower subcharts such as volume and explicit source gaps.

Market-state summary belongs on the dashboard Status page. The Timewheel only needs market/session status where it clarifies the selected time bucket.

`chart_ohlcv_cache` exists to keep the dashboard smooth without retaining every raw fold bar forever. It stores only compact OHLCV buckets and must not be used as training truth.

## Current Limits

The installer upserts `calendar_day`, rule-generated session rows, and accepted official exchange holiday/early-close overlays. Trading Economics monthly source rows and `calendar_observation` artifacts remain source data and do not appear as Timewheel events until a later accepted M06 route explicitly promotes relevant observations into the event-risk or attention pool. Interpreted news artifacts, model event markers, replay state bodies, and chart bars require accepted source-specific producers before they appear as populated detail.
