# Temporal Explorer

`Temporal Explorer` is the shared calendar/timewheel substrate. It is not a traditional month calendar and not a Layer 4-only event list. Its purpose is to align time, market sessions, scheduled events, released results, discovered news, replay/model state, and compact visualization bars on the same inspectable timeline.

## SQL Substrate

| Table | Role |
|---|---|
| `trading_data.calendar_day` | Daily spine from the accepted historical start, one row per date. |
| `trading_data.calendar_market_session` | Venue session state for NYSE, NASDAQ, and `CRYPTO_24_7`. |
| `trading_data.calendar_scheduled_event` | Known-in-advance events. Result values do not belong here. |
| `trading_data.calendar_event_result` | Actual/consensus/surprise payloads after release, with point-in-time clocks. |
| `trading_data.calendar_news_event_index` | News/discovery event index rows with artifact refs, not full raw bodies. |
| `trading_data.chart_ohlcv_cache` | Compact visualization OHLCV cache for dashboard charts. |

## Timewheel Contract

The dashboard Timewheel should consume this substrate through storage read models. It presents:

- top chart viewport centered on the selected time;
- selectable frames: `30m`, `1h`, `1D`, `1W`;
- left lane for market/session/state/replay context;
- center vertical time axis;
- right lane for scheduled/result/news/model event markers.

`chart_ohlcv_cache` exists to keep the dashboard smooth without retaining every raw fold bar forever. It stores only compact OHLCV buckets and must not be used as training truth.

## Current Limits

The deterministic installer can upsert `calendar_day`, rule-generated session rows, and accepted scheduled macro/earnings shell rows already present in `source_10_event_risk_governor`. Early closes, official holiday-source refs, event results, news indexes, and chart bars require accepted source-specific ingestion before they appear as populated lanes.
