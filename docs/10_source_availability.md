# Source Availability

This file records the first public-docs availability inventory for `trading-data` sources. It is not generated data and does not include credentials or provider response dumps.

The inventory exists to support two decisions before connector implementation:

1. which data categories are actually obtainable from approved APIs or official web sources;
2. which `trading-main` `data_kind` rows should be available for task params, validation, output routing, and future storage mapping.

## Availability Rules

- Verify source availability from official documentation or source pages before implementation depends on a data category.
- Use `python -m trading_data.source_availability` for bounded smoke probes after documentation review; default tests for this probe package must not require network access or secrets.
- Register accepted obtainable categories as `kind=data_kind` in `trading-main`.
- Keep `data_bundle` and `data_kind` separate: bundles route execution; data kinds name requested/produced data categories.
- Use one canonical source per economic measure. FRED is limited to FRED/St. Louis Fed/ALFRED-unique data or explicitly approved FRED-native research series/groups.
- Do not store provider credentials, full raw responses, or generated datasets in this repository.

## Probe Workflow

A small stdlib Python probe package now lives under `src/trading_data/source_availability/`.

Common commands:

```bash
PYTHONPATH=src python3 -m trading_data.source_availability --list
PYTHONPATH=src python3 -m trading_data.source_availability --dry-run
PYTHONPATH=src python3 -m trading_data.source_availability --source bls --source us_treasury_fiscal_data
```

Live probe reports are written under `data/storage/source_availability/`, which is ignored by Git. Reports contain probe status fields, HTTP status when available, response shape keys, and tiny sanitized sample rows only. They must not contain request headers, credential values, or full raw provider dumps.

Optional provider secrets are loaded only by local alias from `/root/secrets/<alias>.json`, with registered environment-variable overrides such as `FRED_SECRET_ALIAS`, `BEA_SECRET_ALIAS`, and `ALPACA_SECRET_ALIAS`. Reports may show alias metadata and key names present, but never secret values.


## API-Level Confirmation

Documentation availability is not sufficient for implementation acceptance. The first API-backed acquisition code now lives under `src/trading_data/data_sources/macro_data/` and makes real bounded requests for `bls`, `census`, `bea`, `us_treasury_fiscal_data`, and `fred`.

The macro bundle writes sanitized request evidence, normalized rows, CSV/JSONL development outputs, and a completion receipt under ignored `data/storage/`. It does not persist full raw provider responses by default. The first live smoke runs confirmed these actual response shapes:

- BLS CPI sample (`CUUR0000SA0`) normalizes `year`, `period`, `periodName`, `value`, `footnotes`, and `series_id`.
- Census MARTS sample normalizes array responses using the provider header row, including `data_type_code`, `seasonally_adj`, `category_code`, `cell_value`, `error_data`, `time`, and geography columns.
- BEA NIPA sample normalizes `BEAAPI.Results.Data` rows, including `TableName`, `LineNumber`, `LineDescription`, `SeriesCode`, `TimePeriod`, `DataValue`, units, and metadata fields.
- U.S. Treasury Fiscal Data debt sample normalizes `data[]` rows with record-date/calendar/fiscal fields and amount fields as provider strings.
- FRED native sample normalizes `observations[]` rows with `date`, `value`, and real-time vintage bounds.

Use this implementation path to discover actual source formats before accepting source-specific `macro_data.params` contracts or SQL storage mappings.

## Macro Sources

| Source | Available categories | Access expectation | Notes |
|---|---|---|---|
| FRED / St. Louis Fed | FRED-native research series/groups, FRED metadata, St. Louis Fed series, ALFRED/vintage views when approved. | API key through `FRED_SECRET_ALIAS`. | Do not duplicate official BLS/BEA/Census/Treasury measures by default. |
| ALFRED | Vintage/revision history and point-in-time observations. | FRED API key. | Valuable for backtests; using ALFRED for official-agency measures is an explicit exception path. |
| BLS | CPI/C-CPI, PPI, import/export prices, CES payrolls/earnings/hours, CPS labor force, JOLTS, ECI, productivity. | Public API; registered key enables higher/expanded limits. | Requires source-specific series ID taxonomy. |
| Census | Retail sales, wholesale trade, manufacturing shipments/inventories/orders, durable goods, construction spending, housing construction, new home sales, business formation, international trade. | Public API for small use; key required above published limits. | EITS and trade dimensions need dataset dictionaries. |
| BEA | NIPA/GDP, PCE/income/outlays, GDP by industry, regional, international accounts, fixed assets. | API key through `BEA_SECRET_ALIAS`. | Use BEA metadata methods before ingest. |
| U.S. Treasury Fiscal Data | Debt, Daily Treasury Statement, Monthly Treasury Statement, interest rates, interest expense and related federal finance datasets. | Open/no-key API. | JSON values often require type casting. |
| Official macro pages | Release calendars and release events. | Public web/API varies. | Prefer structured official feeds when available; HTML scraping needs guardrails. |

## Non-Macro Sources

| Source | Available categories | Access expectation | Notes |
|---|---|---|---|
| Alpaca | Equity bars, trades, quotes, snapshots, news. | `ALPACA_SECRET_ALIAS`; entitlement/feed availability must be checked at runtime. | News is its own bundle. |
| ThetaData | Option contracts, trades, quotes/NBBO, OHLC, EOD, open interest, implied volatility, Greeks, trade Greeks, snapshots. | `THETADATA_SECRET_ALIAS`; local terminal/runtime placement still pending. | ThetaData entitlement coverage needs a controlled smoke test after connector design. |
| OKX | Crypto bars; trades, quotes/tickers, and order book are available if later accepted. | Public market endpoints for market data; private endpoints need credentials. | Current accepted bundle remains bars-focused. |
| SEC EDGAR | Submissions, company facts, company concepts, frames, filing document references. | No key; identifying User-Agent and fair-access behavior required. | Use official SEC endpoints only by default. |
| ETF issuers | Holdings rows/snapshots, fund metadata, constituent weights. | Usually public web/file downloads. | No universal API; implement issuer-specific adapters and source URL/as-of tracking. |
| Federal Reserve FOMC page | Meetings, statements, minutes, SEP markers. | Public web. | No stable JSON API confirmed; preserve source URL and retrieval timestamp. |


## Provider/Data-Kind Interface Layer

The source inventory now has an executable provider/data-kind layer under `src/trading_data/source_interfaces/`. This is separate from source-level smoke probes: it maps each obtainable `data_kind` to a concrete source, bundle, endpoint family, access rule, and bounded smoke request.

Common commands:

```bash
PYTHONPATH=src python3 -m trading_data.source_interfaces --list
PYTHONPATH=src python3 -m trading_data.source_interfaces --source alpaca
PYTHONPATH=src python3 -m trading_data.source_interfaces --source okx
PYTHONPATH=src python3 -m trading_data.source_interfaces --source sec_company_financials
PYTHONPATH=src python3 -m trading_data.source_interfaces --source thetadata
```

Live interface reports write under ignored `data/storage/source_interfaces/` and contain sanitized endpoint/status/shape/sample evidence only.

Current API-level findings:

- Alpaca live checks succeeded for `equity_bar`, `equity_trade`, `equity_quote`, `equity_snapshot`, and `equity_news` using the data API endpoint. Response shapes include bars (`t/o/h/l/c/v/vw/n`), trades (`t/p/s/x/i/c/z`), quotes (`t/bp/bs/bx/ap/as/ax/c/z`), snapshots (`latestTrade`, `latestQuote`, `minuteBar`, `dailyBar`, `prevDailyBar`), and news (`headline`, `source`, `url`, `symbols`, timestamps, summary/content/image metadata).
  Persistence rule: raw Alpaca trades/quotes are too large for default retention; they should be transient inputs used to produce ET-aligned aggregate outputs (`equity_trade_bar_derived`, `equity_quote_bar_derived`, `equity_microstructure_bar_derived`).
- OKX live checks succeeded for `crypto_bar`, `crypto_trade`, `crypto_quote`, and `crypto_order_book`. OKX bar rows are positional arrays; trades, tickers, and books are JSON objects under `data[]`.
- SEC EDGAR live checks succeeded for submissions, company facts, company concept, and XBRL frames using Apple CIK / Assets as bounded smoke examples. Companyfacts can be very large, so production code should request only needed concepts or normalize streamed/segmented facts.
- ThetaData Terminal was installed/running locally outside the repo, currently serving v3 on `127.0.0.1:25503`. Live checks succeeded for option contracts, trades, quotes, trade+quote/NBBO, OHLC, EOD, open interest, implied volatility, first-order Greeks, and snapshots. Second-order Greeks, third-order Greeks, and trade Greeks returned entitlement blocks requiring a professional ThetaData subscription; the current account is options STANDARD.
- ETF holdings and official macro release calendars remain adapter-specific web/file sources; no universal API should be assumed.



### ThetaData local runtime note

ThetaData v3 requires Java 21+ and a local Theta Terminal. The local runtime is intentionally outside the Git repository under `/root/tools/thetadata-terminal/`; credentials are generated from `/root/secrets/thetadata.json` into a local `creds.txt` with `0600` permissions and must never be committed. The current terminal config serves REST on `127.0.0.1:25503/v3`.

## Registered Data Kind Groups

Initial `data_kind` rows are registered in `trading-main` for:

- equity market data;
- crypto market data;
- option data;
- SEC EDGAR company financial data;
- ETF holdings;
- FOMC and economic release calendar data;
- macro BLS data;
- macro Census data;
- macro BEA data;
- macro Treasury Fiscal Data;
- FRED-native and ALFRED/vintage data.

Exact source-specific parameter dictionaries remain open work. They should be defined before the first connector implementation for each source.

## Alpaca quotes/trades implementation

`src/trading_data/data_sources/alpaca_quotes_trades/` now contains the first aggregate-only implementation. It requests Alpaca trades and quotes with bounded pagination, treats raw rows as transient run inputs, aligns intervals in `America/New_York`, and persists only derived aggregate outputs:

- `equity_trade_bar_derived` — trade count, volume, notional, OHLC from trades, VWAP, first/last trade timestamps.
- `equity_quote_bar_derived` — quote count, average bid/ask/mid/spread, min/max spread, average sizes, last quote state.
- `equity_microstructure_bar_derived` — interval-level trade/quote combined features such as trade VWAP vs average quote mid.

Current implementation supports `1Min`, `5Min`, `15Min`, `1Hour`, and `1Day` buckets. Raw Alpaca trades/quotes are not written as saved outputs.
