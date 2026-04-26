# alpaca_quotes_trades bundle

Fetches Alpaca raw trades/quotes only as transient run inputs and persists
America/New_York time-bucketed derived aggregate outputs.

Default persisted output:

- `equity_liquidity_bar`

Raw trade/quote rows are not saved by default. Request manifests record sanitized
endpoint evidence and raw counts only.
