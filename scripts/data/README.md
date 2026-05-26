# data acquisition scripts

- `run_trading_economics_recent_calendar_refresh.py` plans or runs the bounded Trading Economics recent/future calendar refresh. It appends canonical storage source rows only and must not persist website URLs or populate Layer 10 SQL rows.
- `install_temporal_explorer_tables.py` installs the provider-neutral Temporal Explorer SQL substrate, upserts deterministic day/session spine rows, and can populate scheduled-event/result/news-index substrate rows from accepted `source_10_event_risk_governor` evidence. It does not call providers or populate chart bars.
