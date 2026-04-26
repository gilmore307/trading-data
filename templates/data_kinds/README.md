# Data Kind Templates

This directory is the source-organized catalog for final saved `trading-data` data kinds. The top level describes data sources and routing; each source folder owns the detailed README and preview CSV files for data kinds produced from that source.

## Scope

Only final used/saved data kinds get preview CSV files. Raw or transient provider rows belong as notes in the owning source README, not as top-level preview files, unless explicitly accepted as saved outputs.

## Layout

```text
templates/data_kinds/
  README.md              Source index and catalog rules.
  alpaca/
    README.md            Alpaca final data-kind details.
    *.preview.csv        Small final-output CSV previews.
  okx/
    README.md            OKX crypto data-kind details.
    *.preview.csv        Small final-output CSV previews.
```

## Sources

| Source | Folder | Final saved data kinds | Notes |
|---|---|---|---|
| Alpaca Market Data API | `alpaca/` | `equity_bar`, `equity_liquidity_bar`, `equity_news` | Raw trades/quotes are transient inputs for `equity_liquidity_bar`; snapshots are non-final until accepted. |
| OKX Market Data API | `okx/` | `crypto_trade`, `crypto_liquidity_bar` previews | OKX is canonical for crypto execution research; quote-derived fields may be blank/null because historical quote parity with Alpaca is not assumed. |

## Source README Fields

Each source folder README should record these fields for every final saved data kind:

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
- **Preview file** — small CSV sample file in the same source folder for the final saved format.
- **Known caveats** — entitlements, exchange conditions, source quirks, large-volume risks, or production-hardening notes.
