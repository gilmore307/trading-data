# 04_feed_okx_crypto_market_data feed

Fetches OKX public crypto market data and writes normalized SQL-only outputs.

Default persisted outputs:

- `trading_data.feed_04_okx_crypto_bar`
- `trading_data.feed_04_okx_crypto_liquidity_bar`

Raw OKX trades are normalized transiently toward an Alpaca-like trade shape, then aggregated into `crypto_liquidity_bar`. Standalone `crypto_trade` is not saved by default because liquidity bars contain the accepted trade-derived features. `crypto_liquidity_bar` leaves quote/order-book derived fields empty unless a reviewed snapshot source adds them. Missing quote features are valid model inputs and are marked with `quote_features_available=false`.
