# data acquisition scripts

- `run_trading_economics_recent_calendar_refresh.py` builds or executes the bounded Trading Economics recent-calendar refresh task for continuously reusable macro/event rows.
- `install_temporal_explorer_tables.py` installs the provider-neutral Temporal Explorer SQL substrate and upserts deterministic day/session spine rows. It does not call providers or populate event results/news/chart bars.
