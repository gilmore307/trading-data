# Feed Interfaces

`feed_interfaces` records executable provider/data-kind interfaces. It is the
next layer after documentation/feed availability: each entry names a concrete
`data_kind`, feed package, endpoint family, access rule, and bounded smoke
parameters.

Commands:

```bash
PYTHONPATH=src python3 -m feed_interfaces --list
PYTHONPATH=src python3 -m feed_interfaces --feed 01_feed_alpaca_bars
PYTHONPATH=src python3 -m feed_interfaces --feed 04_feed_okx_crypto_market_data
PYTHONPATH=src python3 -m feed_interfaces --feed 08_feed_sec_company_financials
PYTHONPATH=src python3 -m feed_interfaces --feed 09_feed_thetadata_option_selection_snapshot
```

Reports write to ignored `storage/feed_interfaces/` unless `--no-write`
is used. Reports include sanitized endpoints, HTTP status, response shape keys,
and tiny samples only. They must not contain credential values or full raw data.

Current implemented interface groups:

- Alpaca: `equity_bar`, `equity_trade`, `equity_quote`, `equity_snapshot`, `equity_news`.
- OKX: `crypto_bar`, `crypto_trade`, `crypto_quote`, `crypto_order_book`.
- ThetaData: option data-kind endpoint families through local v3 terminal on `127.0.0.1:25503`; STANDARD entitlement confirmed for core option history/snapshot data, while professional-only Greeks/trade-Greeks are marked as entitlement-blocked.
- SEC EDGAR: `sec_submission`, `sec_company_fact`, `sec_company_concept`, `sec_xbrl_frame`.
- Calendar/source interfaces: FOMC is directly probeable; Trading Economics
  calendar events, official exchange calendars, Nasdaq earnings-calendar shells,
  official index announcements, and unified `calendar_observation` rows have
  concrete interfaces. ETF holdings use issuer-specific adapters and are not a
  universal calendar/event interface.

## ThetaData local runtime

ThetaData Terminal runtime files are kept outside this repo at `/root/tools/thetadata-terminal/`. The generated `creds.txt` comes from `/root/secrets/thetadata.json`, is permissioned `0600`, and must not be committed or printed. The v3 REST base URL is `http://127.0.0.1:25503/v3`.
