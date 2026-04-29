# 06_feed_etf_holdings feed

`06_feed_etf_holdings` is the official issuer-holdings interface for ETF constituent and portfolio-weight snapshots.

Current scope is a scaffold plus parser/adapter routing boundary; it does not bulk backfill all ETFs yet. The user-owned ETF→issuer mapping will drive future production routing.

Confirmed issuer patterns:

- iShares: official CSV `.ajax?fileType=csv&fileName=<TICKER>_holdings&dataType=fund`.
- State Street/SPDR and Select Sector SPDR: official holdings XLSX under `ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-<ticker>.xlsx`.
- Global X: official dated CSV under `assets.globalxetfs.com/funds/holdings/<ticker>_full-holdings_YYYYMMDD.csv`.
- ARK Invest: official CSV under `assets.ark-funds.com/fund-documents/funds-etf-csv/..._HOLDINGS.csv`.
- First Trust: official HTML holdings table.
- Invesco: official holdings JSON endpoint.
- U.S. Global Investors: official fund-page holdings table.
- Vanguard: official JS-rendered profile holdings table.
- VanEck: official page exposes holdings XLSX download; may require browser/session headers.

Params:

- `etf_symbol` — required.
- `issuer_name` — required until the mapping table is registered. Legacy `issuer` is accepted temporarily at the ingestion boundary for compatibility.
- `source_url` — optional official URL.
- `csv_path` / `csv_text` — optional issuer CSV evidence.
- `html_path` / `html` — optional issuer HTML table evidence.
- `json_path` / `json_text` — optional issuer JSON evidence.

Outputs:

- `request_manifest.json`
- `cleaned/etf_holding_snapshot.jsonl`
- `saved/etf_holding_snapshot.csv`
- `completion_receipt.json`
