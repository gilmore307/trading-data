# Data Kind Catalog

This catalog tracks concrete data kinds that `trading-data` can request, clean,
or produce. It is deliberately **not** a bundle list: bundles are execution
boundaries, while data kinds are the actual data categories available to tasks,
validation, routing, and future storage mapping.

## Catalog Fields

For each data kind, record:

- **Data kind** — registered canonical payload/key, e.g. `equity_bar`.
- **Source** — provider or official source.
- **Bundle** — execution bundle that fetches or produces it.
- **Status** — `live-confirmed`, `implemented`, `derived-implemented`, `entitlement-blocked`, `adapter-needed`, or `planned`.
- **Persistence policy** — whether rows are persisted, aggregated first, transient-only, or debug-only.
- **Earliest available range** — earliest confirmed provider availability or earliest smoke-confirmed sample. Use `unknown` until tested.
- **Default timestamp semantics** — all normalized outputs should expose `America/New_York` timestamps for research workflows; source timestamps may be preserved only when useful and explicitly named.
- **Natural grain** — row granularity such as one bar, one trade, one quote, one article, one contract/day, one interval aggregate.
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

### `equity_trade`

- **Source:** Alpaca Market Data API.
- **Bundle:** `alpaca_quotes_trades`.
- **Status:** `live-confirmed` as source input; not a default persisted output.
- **Persistence policy:** Transient input only by default. Raw trade rows can be streamed/segmented during aggregation and discarded. Persist `equity_trade_bar_derived` instead.
- **Earliest available range:** `unknown`; live smoke confirmed AAPL trades on 2024-01-02 09:30 ET.
- **Default timestamp semantics:** Source trade timestamp converted to ET only in derived outputs/diagnostics.
- **Natural grain:** One trade print.
- **Request parameters:** `symbol`, `start`, `end`; optional `limit`, `max_pages`, `feed`.
- **Pagination/range behavior:** Alpaca `next_page_token`; high row volume requires segmentation.
- **Preview:**

```json
{"t":"2024-01-02T14:30:00.011509342Z","p":187.18,"s":2,"x":"P","i":14920,"c":["@","F","T","I"],"z":"C"}
```

- **Known caveats:** Potentially hundreds/thousands of rows per minute; raw persistence is disabled by policy.

### `equity_quote`

- **Source:** Alpaca Market Data API.
- **Bundle:** `alpaca_quotes_trades`.
- **Status:** `live-confirmed` as source input; not a default persisted output.
- **Persistence policy:** Transient input only by default. Raw quote rows can be streamed/segmented during aggregation and discarded. Persist `equity_quote_bar_derived` and/or `equity_microstructure_bar_derived` instead.
- **Earliest available range:** `unknown`; live smoke confirmed AAPL quotes on 2024-01-02 09:30 ET.
- **Default timestamp semantics:** Source quote timestamp converted to ET only in derived outputs/diagnostics.
- **Natural grain:** One quote/NBBO update.
- **Request parameters:** `symbol`, `start`, `end`; optional `limit`, `max_pages`, `feed`.
- **Pagination/range behavior:** Alpaca `next_page_token`; high row volume requires segmentation.
- **Preview:**

```json
{"t":"2024-01-02T14:30:00.004605455Z","bp":187.1,"bs":30,"bx":"P","ap":187.19,"as":1,"ax":"P","c":["R"],"z":"C"}
```

- **Known caveats:** Raw quote storage explodes quickly. Some live samples can show crossed/odd spread states; aggregation should preserve enough diagnostics such as min/max spread.

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

### `equity_snapshot`

- **Source:** Alpaca Market Data API.
- **Bundle:** `alpaca_quotes_trades` currently catalogs it; no persistence bundle implemented yet.
- **Status:** `live-confirmed`.
- **Persistence policy:** Not yet accepted as a default persisted output. Snapshot should be normalized only when a use case is defined.
- **Earliest available range:** Snapshot/current endpoint only; historical range not applicable.
- **Default timestamp semantics:** Any nested timestamps should be normalized to `America/New_York` when persisted.
- **Natural grain:** One current symbol snapshot containing latest trade, latest quote, minute bar, daily bar, and previous daily bar.
- **Request parameters:** `symbol`.
- **Pagination/range behavior:** No historical pagination for the single-symbol snapshot smoke.
- **Preview shape:**

```json
{"symbol":"AAPL","latestTrade":{},"latestQuote":{},"minuteBar":{},"dailyBar":{},"prevDailyBar":{}}
```

- **Known caveats:** Nested provider shape needs expansion before persistence.

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
