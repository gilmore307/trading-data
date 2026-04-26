# Data Kind Templates

This folder tracks concrete data kinds that `trading-data` will actually use or save as final CSV outputs. It is deliberately **not** a bundle list: bundles are execution
boundaries, while cataloged data kinds here are the final/persisted categories available to tasks, validation, routing, and future storage mapping.

## Scope

Only final used/saved data kinds belong as top-level entries here. High-volume raw provider rows such as raw trades and raw quotes should be documented only as transient source inputs under the final derived data kind that consumes them. Do not create top-level catalog entries for raw/transient data unless the user explicitly accepts that data kind as a saved output.

## README Fields

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
- **Preview file** — small CSV sample file in this folder for the final saved format.
- **Known caveats** — entitlements, exchange conditions, source quirks, large-volume risks, or production-hardening notes.

## Preview Files

Each final data kind should have a small CSV preview file beside this README. The preview is a template/sample of the final saved format, not a raw provider dump. Current previews:

- `equity_bar.preview.csv`
- `equity_liquidity_bar.preview.csv`
- `equity_news.preview.csv`

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
- **Preview file:** see `equity_bar.preview.csv`.

- **Known caveats:** Provider timestamp is UTC; normalized output uses ET. Feed entitlement and full range limits still need broader testing.

## Alpaca transient raw inputs

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
- **Preview file:** see `equity_news.preview.csv`.

- **Known caveats:** Article text may be empty or provider-limited; URLs/images are external references and should be treated as source metadata, not local media assets.
