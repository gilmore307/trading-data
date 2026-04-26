# Data Kind Catalog

This catalog tracks concrete data kinds that `trading-data` will actually use or save as final outputs. It is deliberately **not** a bundle list: bundles are execution
boundaries, while cataloged data kinds here are the final/persisted categories available to tasks, validation, routing, and future storage mapping.

## Scope

Only final used/saved data kinds belong as top-level entries here. High-volume raw provider rows such as raw trades and raw quotes should be documented only as transient source inputs under the final derived data kind that consumes them. Do not create top-level catalog entries for raw/transient data unless the user explicitly accepts that data kind as a saved output.

## Catalog Fields

For each final data kind, record:

- **Data kind** — registered canonical payload/key, e.g. `equity_bar`.
- **Source** — provider or official source.
- **Bundle** — execution bundle that fetches or produces it.
- **Status** — `live-confirmed`, `implemented`, `derived-implemented`, `entitlement-blocked`, `adapter-needed`, or `planned`.
- **Persistence policy** — how the final data is saved; raw/transient inputs are source notes, not catalog entries.
- **Earliest available range** — earliest confirmed provider availability or earliest smoke-confirmed sample. Use `unknown` until tested.
- **Default timestamp semantics** — all normalized outputs should expose `America/New_York` timestamps for research workflows; source timestamps may be preserved only when useful and explicitly named.
- **Natural grain** — row granularity such as one saved bar, one article, one contract/day, or one interval aggregate.
- **Request parameters** — required and important optional params.
- **Pagination/range behavior** — pagination token, date segmentation, symbol segmentation, or source-specific range limits.
- **Preview** — tiny sanitized sample row or shape from live smoke/implementation.
- **Known caveats** — entitlements, exchange conditions, source quirks, large-volume risks, or production-hardening notes.

## Alpaca

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
- **Preview:**

```json
{"data_kind":"equity_bar","symbol":"AAPL","timeframe":"1Day","timestamp_et":"2024-01-02T00:00:00-05:00","open":187.15,"high":188.44,"low":183.885,"close":185.64,"volume":82496943,"vwap":185.846233,"trade_count":1009074}
```

- **Known caveats:** Provider timestamp is UTC; normalized output uses ET. Feed entitlement and full range limits still need broader testing.

## Alpaca transient raw inputs

Raw `equity_trade` and `equity_quote` source rows are live-confirmed but are **not** final saved data kinds for this project. They are high-volume transient inputs consumed by `alpaca_quotes_trades` to produce the final derived data kinds below.

- Raw trades preview shape: `t`, `p`, `s`, `x`, `i`, `c`, `z`.
- Raw quotes preview shape: `t`, `bp`, `bs`, `bx`, `ap`, `as`, `ax`, `c`, `z`.
- Persistence rule: stream or segment during aggregation, then discard by default.
- Reason: raw trade/quote rows can reach hundreds or thousands of rows per minute and would overwhelm storage over longer histories.

### `equity_trade_bar_derived`

- **Source:** Derived from Alpaca `equity_trade`.
- **Bundle:** `alpaca_quotes_trades`.
- **Status:** `derived-implemented`.
- **Persistence policy:** Persisted default output for trade-derived information.
- **Earliest available range:** Same as `equity_trade`; implementation live-confirmed AAPL 2024-01-02 09:30 ET.
- **Default timestamp semantics:** `interval_start_et` in `America/New_York`.
- **Natural grain:** One symbol/timeframe ET interval aggregate.
- **Request parameters:** Parent task uses `symbol`, `start`, `end`, `timeframe`; optional `limit`, `max_pages`, `feed`.
- **Pagination/range behavior:** Aggregates paginated transient trades into ET buckets.
- **Preview:**

```json
{"data_kind":"equity_trade_bar_derived","symbol":"AAPL","timeframe":"1Min","interval_start_et":"2024-01-02T09:30:00-05:00","trade_count":1000,"trade_volume":53862,"trade_vwap":187.0966001819,"trade_open":187.18,"trade_high":187.25,"trade_low":186.35,"trade_close":187.06}
```

- **Known caveats:** Current first implementation computes basic trade OHLC/VWAP/count/volume. Later filters may exclude conditions or odd lots.

### `equity_quote_bar_derived`

- **Source:** Derived from Alpaca `equity_quote`.
- **Bundle:** `alpaca_quotes_trades`.
- **Status:** `derived-implemented`.
- **Persistence policy:** Persisted default output for quote-derived information.
- **Earliest available range:** Same as `equity_quote`; implementation live-confirmed AAPL 2024-01-02 09:30 ET.
- **Default timestamp semantics:** `interval_start_et` in `America/New_York`.
- **Natural grain:** One symbol/timeframe ET interval aggregate.
- **Request parameters:** Parent task uses `symbol`, `start`, `end`, `timeframe`; optional `limit`, `max_pages`, `feed`.
- **Pagination/range behavior:** Aggregates paginated transient quotes into ET buckets.
- **Preview:**

```json
{"data_kind":"equity_quote_bar_derived","symbol":"AAPL","timeframe":"1Min","interval_start_et":"2024-01-02T09:30:00-05:00","quote_count":1000,"avg_bid":187.06611,"avg_ask":187.09592,"avg_mid":187.081015,"avg_spread":0.02981,"last_bid":187.0,"last_ask":187.05,"last_mid":187.025}
```

- **Known caveats:** Current implementation uses simple interval averages, not time-weighted quote state. Time-weighted variants should be explicitly registered/implemented if needed.

### `equity_microstructure_bar_derived`

- **Source:** Derived from Alpaca trades and quotes.
- **Bundle:** `alpaca_quotes_trades`.
- **Status:** `derived-implemented`.
- **Persistence policy:** Persisted default output for bar-aligned microstructure features.
- **Earliest available range:** Same as Alpaca trades/quotes; implementation live-confirmed AAPL 2024-01-02 09:30 ET.
- **Default timestamp semantics:** `interval_start_et` in `America/New_York`.
- **Natural grain:** One symbol/timeframe ET interval aggregate.
- **Request parameters:** Parent task uses `symbol`, `start`, `end`, `timeframe`; optional `limit`, `max_pages`, `feed`.
- **Pagination/range behavior:** Combines trade and quote aggregate rows by interval.
- **Preview:**

```json
{"data_kind":"equity_microstructure_bar_derived","symbol":"AAPL","timeframe":"1Min","interval_start_et":"2024-01-02T09:30:00-05:00","trade_count":1000,"quote_count":1000,"trade_volume":53862,"trade_vwap":187.0966001819,"avg_mid":187.081015,"avg_spread":0.02981,"vwap_minus_avg_mid":0.0155851819}
```

- **Known caveats:** Current implementation is interval-level alignment, not tick-level previous-quote matching. Effective/realized spread and trade-sign rules need separate explicit design.

## Alpaca non-final snapshot

`equity_snapshot` is live-confirmed but is not currently accepted as a final saved data kind. If a concrete use case appears, it should be normalized into an explicit final data kind before being added as a top-level catalog entry.

### `equity_news`

- **Source:** Alpaca News API.
- **Bundle:** `alpaca_news`.
- **Status:** `implemented`.
- **Persistence policy:** Persist cleaned final article metadata/content references. Do not persist full raw provider payloads by default.
- **Earliest available range:** `unknown`; live implementation confirmed AAPL news around 2024-01-09.
- **Default timestamp semantics:** `created_at_et` and `updated_at_et` in `America/New_York`.
- **Natural grain:** One news article/item.
- **Request parameters:** `symbols`, `start`, `end`; optional `limit`, `max_pages`.
- **Pagination/range behavior:** Alpaca `next_page_token`; implementation uses bounded `max_pages`.
- **Preview:**

```json
{"data_kind":"equity_news","id":36564250,"headline":"Bank Of America Predicts 10 2024 Market Surprises: From Booming IPOs To Japanese Equity Surge","source":"benzinga","author":"Piero Cingari","created_at_et":"2024-01-09T14:46:19-05:00","updated_at_et":"2024-01-09T14:46:19-05:00","symbols":["AAPL","EWJ","IHE","KBE","NVDA"],"summary":"Bank of America lists 10 market surprises...","url":"https://www.benzinga.com/...","image_count":3}
```

- **Known caveats:** Article text may be empty or provider-limited; URLs/images are external references and should be treated as source metadata, not local media assets.
