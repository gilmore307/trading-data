# Data Kind Templates

This directory is the source-organized catalog for final saved `trading-data` data kinds. The top level describes data sources and routing; each source folder owns the detailed README and generated preview CSV/JSON files for data kinds produced from that source.

Preview files are the materialized output templates. CSV previews are shaped as the future long-term SQL table rows; table/file names own fixed data kind/source context, so per-table CSVs do not repeat those fields unless the table itself is mixed. They are generated from stable registry ids by `src/trading_data/template_generators/data_kind_previews.py`; do not hand-edit preview CSV/JSON files directly.

## Scope

Only final used/saved data kinds get preview CSV/JSON files. Raw or transient provider rows belong as notes in the owning source README, not as top-level preview files, unless explicitly accepted as saved outputs.

## Layout

```text
storage/templates/data_kinds/
  README.md              Source index and catalog rules.
  macro/
    README.md            Macro release-event table details.
    *.preview.csv        SQL-shaped sparse macro release rows.
  alpaca/
    README.md            Alpaca final data-kind details.
    *.preview.csv        Generated small final-output CSV templates/previews.
  okx/
    README.md            OKX crypto data-kind details.
    *.preview.csv        Generated small final-output CSV templates/previews.
  thetadata/
    README.md            ThetaData option data-kind details.
    *.preview.csv/json   Generated small final-output templates/previews.
```

## Sources

| Source | Folder | Final saved data kinds | Notes |
|---|---|---|---|
| Official macro providers | `macro/` | `macro_release` | Sparse release-event storage; training jobs expand to daily Parquet feature matrices. |
| Alpaca Market Data API | `alpaca/` | `equity_bar`, `equity_liquidity_bar`, `equity_news` | Raw trades/quotes are transient inputs for `equity_liquidity_bar`; snapshots are non-final until accepted. |
| OKX Market Data API | `okx/` | `crypto_bar`, `crypto_liquidity_bar` | OKX is canonical for crypto execution research; raw trades are transient inputs to liquidity bars and quote-derived fields may be blank/null because historical quote parity with Alpaca is not assumed. |
| ThetaData Terminal v3 | `thetadata/` | `option_chain_snapshot`, `option_bar`, `option_activity_event`, `option_activity_event_detail` | Option outputs are split by use case: selection snapshot, specified-contract tracking, and event timeline. Nested contexts are stored as JSON text columns inside CSV previews until SQL JSONB storage exists. |

## Source README Fields

Each source folder README should record these fields for every final saved data kind:

- **Data kind** — registered canonical payload/key, e.g. `equity_bar`; for SQL-shaped per-table CSV previews this is owned by the file/table name and normally not repeated as a column.
- **Source** — provider or official source.
- **Bundle** — execution bundle that fetches or produces it.
- **Status** — `live-confirmed`, `implemented`, `derived-implemented`, `entitlement-blocked`, `adapter-needed`, or `planned`.
- **Persistence policy** — how the final data is saved; raw/transient inputs are source notes, not catalog entries.
- **Earliest available range** — earliest confirmed provider availability or earliest smoke-confirmed sample. Use `unknown` until tested.
- **Default timestamp semantics** — all normalized outputs should expose `America/New_York` timestamps for research workflows; source timestamps may be preserved only when useful and explicitly named.
- **Natural grain** — row granularity such as one saved bar, one article, one contract/day, or one interval aggregate.
- **Request parameters** — required and important optional params.
- **Pagination/range behavior** — pagination token, date segmentation, symbol segmentation, or source-specific range limits.
- **Preview file** — generated small CSV/JSON template file in the same source folder for the final saved format.
- **Known caveats** — entitlements, exchange conditions, source quirks, large-volume risks, or production-hardening notes.
