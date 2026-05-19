# 06_feed_etf_holdings

Official issuer-holdings feed for ETF constituent and portfolio-weight snapshots.

## Purpose

Normalize issuer-published ETF holdings evidence into `etf_holding_snapshot` rows. The feed is adapter-routed by issuer and intentionally preserves source URL, as-of date, retrieval time, and source format.

## Confirmed issuer patterns

- iShares: official CSV `.ajax?fileType=csv&fileName=<TICKER>_holdings&dataType=fund` when a reviewed product id is supplied.
- State Street/SPDR and Select Sector SPDR: official holdings XLSX under `ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-<ticker>.xlsx`.
- Global X: official dated CSV under `assets.globalxetfs.com/funds/holdings/<ticker>_full-holdings_YYYYMMDD.csv`.
- ARK Invest: official CSV under `assets.ark-funds.com/fund-documents/funds-etf-csv/..._HOLDINGS.csv`.
- First Trust: official HTML holdings table.
- Invesco: official holdings JSON endpoint.
- U.S. Global Investors: official fund-page holdings table.
- Vanguard: official JS-rendered profile holdings table.
- VanEck: official page exposes holdings XLSX download and may require ordinary browser/session headers.

## Params

- `etf_symbol` — required.
- `issuer_name` — required until a reviewed ETF-to-issuer mapping table is active. `issuer` is accepted at the ingestion boundary as a compatibility alias.
- `source_url` — optional official URL. If omitted, accepted issuer adapters derive fixed official URLs for State Street/SPDR, Global X, ARK Invest, and First Trust from `etf_symbol` plus `issuer_name`.
- `csv_path` / `csv_text` — optional issuer CSV evidence.
- `html_path` / `html` — optional issuer HTML evidence.
- `json_path` / `json_text` — optional issuer JSON evidence.

## Outputs

```text
request_manifest.json
cleaned/etf_holding_snapshot.jsonl
saved/etf_holding_snapshot.csv
completion_receipt.json
```

Only final normalized holdings rows are saved by default. Raw source files/pages are input evidence and should not be copied into Git.
