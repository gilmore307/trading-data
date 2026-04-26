# okx_crypto_market_data bundle

Fetches OKX public crypto market data and saves normalized CSV final outputs.

Default persisted outputs:

- `crypto_bar`
- `crypto_liquidity_bar`

Raw OKX trades are normalized transiently toward an Alpaca-like trade shape, then aggregated into `crypto_liquidity_bar`. Standalone `crypto_trade` is not saved by default because liquidity bars contain the accepted trade-derived features. `crypto_liquidity_bar` leaves quote/order-book derived fields empty unless a future snapshot source is explicitly added. Missing quote features are valid model inputs and are marked with `quote_features_available=false`.
