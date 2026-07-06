# systemd units

`trading-data-equity-total-symbol-pool-refresh.service` and `.timer` refresh the
realtime equity total-symbol pool every 30 minutes from the TradingView top-300
traded-dollar-value and top-300 market-cap screener snapshot. The refresh does
not fetch ETF holdings and is not historical replay candidate evidence. Optional environment
overrides belong in `/etc/default/trading-data-equity-total-symbol-pool-refresh`;
`TRADING_DATA_EQUITY_POOL_PER_RANK_LIMIT` defaults to `300`.

`trading-data-calendar-maintenance.service` and `.timer` run bounded calendar
source maintenance:

- Trading Economics recent/future macro calendar preview discovery once per day,
  with source buckets written only for new or changed TE facts;
- a shared Trading Economics release-fetch queue updated from known future
  release times;
- Nasdaq earnings schedule discovery into official calendar artifacts.

`trading-data-te-release-fetch.service` and `.timer` are the single shared
release-fetch worker. The timer wakes the worker once per minute. The worker
loads the queue, processes due release windows, polls TE every 5 seconds for up
to 60 seconds, and writes provisional web-search fallback evidence only if no
formal TE actual appears.

The service writes source rows/artifacts only. It must not persist Trading
Economics website URLs or populate M03 event-state or event-effect SQL rows.

Optional environment overrides belong in `/etc/default/trading-data-calendar-maintenance`.
`TRADING_DATA_CALENDAR_SYMBOLS_FILE` may point to a comma- or newline-delimited
stock-pool file; when unset, the Nasdaq earnings schedule refresh stores all
returned rows for the bounded dates.

The checked-in service defaults `TRADING_DATA_CALENDAR_SYMBOLS_FILE` to
`/root/projects/trading-storage/main/shared/equity_total_symbol_pool.symbols.txt`.
If that file is absent, calendar maintenance continues with an empty symbol
filter. The checked-in timer runs calendar maintenance daily; it does not run
hourly. Trading Economics no-op refreshes are cleaned up instead of leaving
run receipts or duplicate source byproducts.
