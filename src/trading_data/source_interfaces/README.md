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

Reports write to ignored `data/storage/source_interfaces/` unless `--no-write`
is used. Reports include sanitized endpoints, HTTP status, response shape keys,
and tiny samples only. They must not contain credential values or full raw data.

Current implemented interface groups:

- Alpaca: `equity_bar`, `equity_trade`, `equity_quote`, `equity_snapshot`, `equity_news`.
- OKX: `crypto_bar`, `crypto_trade`, `crypto_quote`, `crypto_order_book`.
- ThetaData: option data-kind endpoint families, blocked until local Theta Terminal is reachable.
- SEC EDGAR: `sec_submission`, `sec_company_fact`, `sec_company_concept`, `sec_xbrl_frame`.
- Calendar/ETF placeholders: official FOMC page is directly probeable; ETF holdings and official release calendars require source-specific adapters.
