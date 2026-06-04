# systemd units

`trading-data-equity-total-symbol-pool-refresh.service` and `.timer` refresh the
realtime equity total-symbol pool every 30 minutes from the TradingView top-300
volume and top-300 market-cap screener snapshot. The refresh does not fetch ETF
holdings and is not historical replay candidate evidence. Optional environment
overrides belong in `/etc/default/trading-data-equity-total-symbol-pool-refresh`;
`TRADING_DATA_EQUITY_POOL_PER_RANK_LIMIT` defaults to `300`.

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

The checked-in service defaults `TRADING_DATA_CALENDAR_SYMBOLS_FILE` to
`/root/projects/trading-storage/main/shared/equity_total_symbol_pool.symbols.txt`.
If that file is absent, calendar maintenance continues with an empty symbol
filter rather than failing the Trading Economics refresh.
