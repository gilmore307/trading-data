# OKX Data Kind Templates

OKX is the canonical crypto market-data source for this project because crypto execution is on OKX. Alpaca crypto may be used later as a cross-check, but OKX owns default crypto research and execution-aligned features.

## Normalization rule

Normalize OKX crypto rows to the same model-facing market-data shape used by Alpaca. Avoid OKX-specific final columns unless they are necessary; source-specific raw fields remain transient. Missing quote-derived fields are expected and meaningful: models must tolerate partial feature availability instead of assuming every source has historical quote rows.

### `crypto_bar`

- **Source:** OKX public market data API.
- **Bundle:** `okx_crypto_market_data`.
- **Status:** `implemented`.
- **Persistence policy:** Persist cleaned final OHLCV candle rows as CSV only. Do not persist raw provider payloads by default once a pipeline exists.
- **Earliest available range:** `unknown`; live preview confirmed current BTC-USDT candles.
- **Default timestamp semantics:** Convert OKX millisecond candle `ts` to `timestamp_utc` and `timestamp_et`.
- **Natural grain:** One crypto candle per instrument/timeframe/timestamp.
- **Request parameters:** `instId`, `timeframe`; optional `limit`.
- **Pagination/range behavior:** Current implementation fetches bounded recent candles; broader historical range behavior must be verified before backfill claims.
- **Preview file:** see `crypto_bar.preview.csv`.
- **Known caveats:** OKX raw candle rows are positional arrays; normalize before model use.

## Transient Raw Inputs

Raw OKX `crypto_trade` source rows are live-confirmed but are **not** final saved data kinds for this project. They are normalized transiently toward an Alpaca-like trade shape, consumed by `okx_crypto_market_data`, and aggregated into `crypto_liquidity_bar`.

- Raw trade preview shape: `instId`, `side`, `sz`, `px`, `source`, `tradeId`, `ts`.
- Transient normalized shape may include provider/debug context such as `source`, but final SQL-shaped saved templates omit fixed table/source discriminator columns.
- Persistence rule: keep only run-local cleaned transient JSONL while building liquidity bars; do not save standalone `crypto_trade.csv` by default.
- Reason: `crypto_liquidity_bar` contains the accepted trade-derived final features, so saving both duplicates storage.

### `crypto_liquidity_bar`

- **Source:** Derived from OKX trades, with quote/order-book features nullable unless sampled snapshots are available.
- **Bundle:** `okx_crypto_market_data`.
- **Status:** `derived-implemented`.
- **Persistence policy:** Persist cleaned final interval rows as CSV only. Quote-derived fields may be blank/null by design.
- **Earliest available range:** Trade-derived portions follow OKX trade availability; quote/order-book portions are available only from collected snapshots unless a historical order-book source is accepted.
- **Default timestamp semantics:** `interval_start_et` in `America/New_York`; source trade timestamps are UTC milliseconds before normalization.
- **Natural grain:** One instrument/timeframe ET interval aggregate.
- **Request parameters:** `instId`, `start`, `end`, `timeframe`; optional snapshot source/sampling cadence if quote/order-book features are included.
- **Pagination/range behavior:** Trade-derived features can be paginated/segmented if historical endpoint behavior supports it; quote/order-book fields are nullable without sampled snapshots.
- **Preview file:** see `crypto_liquidity_bar.preview.csv`.
- **Known caveats:** This intentionally does not require quote parity with Alpaca `equity_liquidity_bar`. Missing quote features are valid inputs, and model code must handle them explicitly.
