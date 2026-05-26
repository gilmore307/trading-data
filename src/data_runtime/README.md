# Data Runtime

Shared runtime helpers for `trading-data` feeds and sources.

- `config.py` owns environment-overridable local path defaults.
- `exchange_calendar.py` owns narrow US equity session-open timing for point-in-time availability. It is not yet a full calendar/market-structure event evidence engine for Layer 4.
- `temporal_explorer.py` owns the accepted calendar/timewheel SQL substrate: the daily spine, venue market-session rows, scheduled-event rows, post-release result rows, news-event index rows, and chart OHLCV cache table definitions.
- `provider_policy.py` owns fail-closed live-provider execution checks.
- `io.py` owns atomic text/JSON writes and run-scoped receipt writes.

This package must stay provider-neutral. Feed/source modules import it before using credentials, network clients, or receipt files.
