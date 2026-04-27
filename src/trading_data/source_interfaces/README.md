# Source Interfaces

`source_interfaces` records executable provider/data-kind interfaces. It is the
next layer after documentation/source availability: each entry names a concrete
`data_kind`, source, bundle, endpoint family, access rule, and bounded smoke
parameters.

Commands:

```bash
PYTHONPATH=src python3 -m trading_data.source_interfaces --list
PYTHONPATH=src python3 -m trading_data.source_interfaces --source alpaca
PYTHONPATH=src python3 -m trading_data.source_interfaces --source okx
PYTHONPATH=src python3 -m trading_data.source_interfaces --source sec_company_financials
PYTHONPATH=src python3 -m trading_data.source_interfaces --source thetadata
```

Reports write to ignored `storage/source_interfaces/` unless `--no-write`
is used. Reports include sanitized endpoints, HTTP status, response shape keys,
and tiny samples only. They must not contain credential values or full raw data.

Current implemented interface groups:

- Alpaca: `equity_bar`, `equity_trade`, `equity_quote`, `equity_snapshot`, `equity_news`.
- OKX: `crypto_bar`, `crypto_trade`, `crypto_quote`, `crypto_order_book`.
- ThetaData: option data-kind endpoint families through local v3 terminal on `127.0.0.1:25503`; STANDARD entitlement confirmed for core option history/snapshot data, while professional-only Greeks/trade-Greeks are marked as entitlement-blocked.
- SEC EDGAR: `sec_submission`, `sec_company_fact`, `sec_company_concept`, `sec_xbrl_frame`.
- Calendar/ETF placeholders: official FOMC page is directly probeable; ETF holdings and official release calendars require source-specific adapters.

## ThetaData local runtime

ThetaData Terminal runtime files are kept outside this repo at `/root/tools/thetadata-terminal/`. The generated `creds.txt` comes from `/root/secrets/thetadata.json`, is permissioned `0600`, and must not be committed or printed. The v3 REST base URL is `http://127.0.0.1:25503/v3`.
