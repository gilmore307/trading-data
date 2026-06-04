# systemd units

`trading-data-calendar-maintenance.service` and `.timer` run bounded calendar
source maintenance:

- Trading Economics recent/future macro calendar refresh into canonical storage
  source rows;
- Nasdaq earnings schedule discovery into official calendar artifacts.

The service writes source rows/artifacts only. It must not persist Trading
Economics website URLs or populate Layer 10 SQL event rows.

Optional environment overrides belong in `/etc/default/trading-data-calendar-maintenance`.
`TRADING_DATA_CALENDAR_SYMBOLS_FILE` may point to a comma- or newline-delimited
stock-pool file; when unset, the Nasdaq earnings schedule refresh stores all
returned rows for the bounded dates.
