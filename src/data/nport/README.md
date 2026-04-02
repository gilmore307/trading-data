# nport adapter family

This directory contains SEC Form N-PORT-specific discovery, extraction, normalization, and refresh workflows for ETF holdings context data.

Use this directory for:
- N-PORT availability checks
- quarterly package discovery
- metadata/package download helpers
- ETF -> SEC series candidate mapping
- ETF holdings extraction from N-PORT package tables
- monthly ETF holdings refresh workflows for the target ETF universe

This family owns the ETF holdings context path.
It should produce the month-partitioned ETF -> constituent mapping outputs under:
- `context/etf_holdings/<YYMM>/<ETF>_<YYMM>.md`

Helper artifacts belong under:
- `context/etf_holdings/_aux/`
