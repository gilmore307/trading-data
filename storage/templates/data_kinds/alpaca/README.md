# Alpaca Data Kind Templates

### `equity_bar`

- **Source:** Alpaca Market Data API.
- **Bundle:** `alpaca_bars`.
- **Status:** `implemented`.
- **Persistence policy:** Persist cleaned final `equity_bar` outputs. Do not persist full raw provider payloads by default.
- **Earliest available range:** `unknown`; live implementation confirmed AAPL daily bars for 2024-01-02 through 2024-01-03. Full historical entitlement/range should be tested by feed/timeframe later.
- **Default timestamp semantics:** `timestamp_et` normalized to `America/New_York`.
- **Natural grain:** One OHLCV bar per symbol/timeframe/timestamp.
- **Request parameters:** `symbol`, `timeframe`, `start`, `end`; optional `limit`, `max_pages`, `adjustment`, `feed`.
- **Pagination/range behavior:** Alpaca `next_page_token`; implementation uses bounded `max_pages`.
- **Preview file:** see `equity_bar.preview.csv`.

- **Known caveats:** Provider timestamp is UTC; normalized output uses ET. Feed entitlement and full range limits still need broader testing.

## Transient Raw Inputs

Raw `equity_trade` and `equity_quote` source rows are live-confirmed but are **not** final saved data kinds for this project. They are high-volume transient inputs consumed by `alpaca_liquidity` to produce the final derived data kinds below.

- Raw trades preview shape: `t`, `p`, `s`, `x`, `i`, `c`, `z`.
- Raw quotes preview shape: `t`, `bp`, `bs`, `bx`, `ap`, `as`, `ax`, `c`, `z`.
- Persistence rule: stream or segment during aggregation, then discard by default.
- Reason: raw trade/quote rows can reach hundreds or thousands of rows per minute and would overwhelm storage over longer histories.

### `equity_liquidity_bar`

- **Source:** Derived from transient Alpaca trades and quotes.
- **Bundle:** `alpaca_liquidity`.
- **Status:** `derived-implemented`.
- **Persistence policy:** Persisted default output for trade/quote liquidity information. Raw trade and quote rows are discarded by default after aggregation.
- **Earliest available range:** Same as Alpaca trades/quotes; implementation live-confirmed AAPL 2024-01-02 09:30 ET.
- **Default timestamp semantics:** `interval_start_et` in `America/New_York`.
- **Natural grain:** One symbol/timeframe ET interval aggregate.
- **Request parameters:** Parent task uses `symbol`, `start`, `end`, `timeframe`; optional `limit`, `max_pages`, `feed`.
- **Pagination/range behavior:** Aggregates paginated transient trades and quotes into one ET bucketed output.
- **Preview file:** see `equity_liquidity_bar.preview.csv`.

- **Known caveats:** Current implementation is interval-level trade/quote aggregation, not tick-level previous-quote matching. Effective/realized spread, trade-sign rules, and time-weighted quote features need separate explicit design.

## Non-final Snapshot

`equity_snapshot` is live-confirmed but is not currently accepted as a final saved data kind. If a concrete use case appears, it should be normalized into an explicit final data kind before being added as a top-level catalog entry.

### `equity_news`

- **Source:** Alpaca News API.
- **Bundle:** `alpaca_news`.
- **Status:** `implemented`.
- **Persistence policy:** Persist cleaned final event/news timeline rows only. Do not persist full raw provider payloads by default.
- **Earliest available range:** `unknown`; live implementation confirmed AAPL news around 2024-01-09.
- **Default timestamp semantics:** `created_at_et` and `updated_at_et` in `America/New_York`.
- **Natural grain:** One news article/item using the shared model-facing timeline fields: `data_kind`, `id`, `headline`, `created_at_et`, `updated_at_et`, `symbols`, `summary`, `url`.
- **Request parameters:** `symbols`, `start`, `end`; optional `limit`, `max_pages`.
- **Pagination/range behavior:** Alpaca `next_page_token`; implementation uses bounded `max_pages`.
- **Preview file:** see `equity_news.preview.csv`.

- **Known caveats:** Article text may be empty or provider-limited. `url` links back to the original article. Provider byline/source/image metadata is intentionally omitted from the model-facing final row unless a later model need proves it useful.
