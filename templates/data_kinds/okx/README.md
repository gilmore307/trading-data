# OKX Data Kind Templates

OKX is the canonical crypto market-data source for this project because crypto execution is on OKX. Alpaca crypto may be used later as a cross-check, but OKX owns default crypto research and execution-aligned features.

## Normalization rule

Normalize OKX crypto rows toward the Alpaca-like market-data shape where practical so downstream models can share feature code across asset/source families. Missing quote-derived fields are expected and meaningful: models must tolerate partial feature availability instead of assuming every source has historical quote rows.

### `crypto_trade`

- **Source:** OKX public market data API.
- **Bundle:** `okx_bars` for current planning; a narrower OKX crypto bundle can be registered when implementation is accepted.
- **Status:** `preview-confirmed`.
- **Persistence policy:** Candidate final saved normalized trade rows. Do not persist raw provider payloads by default once a pipeline exists.
- **Earliest available range:** `unknown`; live preview confirmed current BTC-USDT trades.
- **Default timestamp semantics:** Convert OKX millisecond `ts` to `timestamp_utc` and `timestamp_et`.
- **Natural grain:** One crypto trade print.
- **Request parameters:** `instId`, optional `limit`; historical/pagination range requires further endpoint-range testing.
- **Pagination/range behavior:** OKX REST returns recent trades; historical depth/range behavior must be verified before backfill claims.
- **Preview file:** see `crypto_trade.preview.csv`.
- **Known caveats:** OKX raw values are strings; normalize numeric columns explicitly. OKX `side` is already `buy`/`sell`; Alpaca crypto `tks` maps from `B`/`S` if cross-source normalization is needed.

### `crypto_liquidity_bar`

- **Source:** Derived from OKX trades, with quote/order-book features nullable unless sampled snapshots are available.
- **Bundle:** `okx_bars` for current planning; a narrower OKX liquidity bundle can be registered when implementation is accepted.
- **Status:** `preview-planned`.
- **Persistence policy:** Candidate final saved interval row for crypto liquidity features. Quote-derived fields may be blank/null by design.
- **Earliest available range:** Trade-derived portions follow OKX trade availability; quote/order-book portions are available only from collected snapshots unless a historical order-book source is accepted.
- **Default timestamp semantics:** `interval_start_et` in `America/New_York`; source trade timestamps are UTC milliseconds before normalization.
- **Natural grain:** One instrument/timeframe ET interval aggregate.
- **Request parameters:** `instId`, `start`, `end`, `timeframe`; optional snapshot source/sampling cadence if quote/order-book features are included.
- **Pagination/range behavior:** Trade-derived features can be paginated/segmented if historical endpoint behavior supports it; quote/order-book fields are nullable without sampled snapshots.
- **Preview file:** see `crypto_liquidity_bar.preview.csv`.
- **Known caveats:** This intentionally does not require quote parity with Alpaca `equity_liquidity_bar`. Missing quote features are valid inputs, and model code must handle them explicitly.
