# Temporal Explorer

`Temporal Explorer` is the shared calendar/timewheel substrate. Its purpose is to align time, market sessions, replay/model state, and compact visualization bars on the same inspectable timeline.

## SQL Substrate

| Table | Role |
|---|---|
| `trading_data.calendar_day` | Daily spine from the accepted historical start, one row per date. |
| `trading_data.calendar_market_session` | Venue session state for NYSE, NASDAQ, and `CRYPTO_24_7`. |
| `trading_data.chart_ohlcv_cache` | Compact visualization OHLCV cache for dashboard charts. |

## Timewheel Contract

The dashboard Timewheel should consume this substrate through storage read models. It presents:

- primary chart viewport centered on the selected time;
- selectable frames: `30m`, `1h`, `1D`, `1W`;
- chart x-axis used as the Timewheel axis;
- lower subcharts such as volume and explicit source gaps.

Market-state summary belongs on the dashboard Status page. The Timewheel only needs market/session status where it clarifies the selected time bucket.

`chart_ohlcv_cache` exists to keep the dashboard smooth without retaining every raw fold bar forever. It stores only compact OHLCV buckets and must not be used as training truth.

## Current Limits

The deterministic installer only upserts `calendar_day` and rule-generated session rows. Trading Economics monthly source rows remain storage source data and do not appear as Timewheel events until a later accepted Layer 10 route explicitly promotes macro events into the event-risk or attention pool. Early closes, official holiday-source refs, interpreted news artifacts, model event markers, replay state bodies, and chart bars require accepted source-specific producers before they appear as populated detail.
