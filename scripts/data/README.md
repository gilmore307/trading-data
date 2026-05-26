# data acquisition scripts

- `run_trading_economics_recent_calendar_refresh.py` returns the retired Trading Economics recent-refresh receipt. It performs no provider calls; macro source data comes from the canonical `trading-storage` TE snapshot.
- `install_temporal_explorer_tables.py` installs the provider-neutral Temporal Explorer SQL substrate, upserts deterministic day/session spine rows, and can populate scheduled-event/result/news-index substrate rows from accepted `source_10_event_risk_governor` evidence. It does not call providers or populate chart bars.
