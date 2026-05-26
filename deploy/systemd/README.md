# systemd units

`trading-data-te-calendar-refresh.service` and `.timer` run the bounded
Trading Economics recent/future calendar refresh. The route writes canonical
storage source rows only; it must not persist website URLs or populate Layer 10
SQL event rows.
