# okx_crypto_market_data bundle

Fetches OKX public crypto market data and saves normalized CSV final outputs.

Default persisted outputs:

- `crypto_bar`
- `crypto_trade`
- `crypto_liquidity_bar`

`crypto_trade` is normalized toward the Alpaca-like trade shape. `crypto_liquidity_bar`
uses trade-derived interval features and leaves quote/order-book derived fields empty
unless a future snapshot source is explicitly added. Missing quote features are valid
model inputs and are marked with `quote_features_available=false`.
