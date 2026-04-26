# alpaca_quotes_trades bundle

Fetches Alpaca raw trades/quotes only as transient run inputs and persists
America/New_York time-bucketed derived aggregate outputs.

Default persisted outputs:

- `equity_trade_bar_derived`
- `equity_quote_bar_derived`
- `equity_microstructure_bar_derived`

Raw trade/quote rows are not saved by default. Request manifests record sanitized
endpoint evidence and raw counts only.
