# Source Availability

This file records the first public-docs availability inventory for `trading-data` sources. It is not generated data and does not include credentials or provider response dumps.

The inventory exists to support two decisions before connector implementation:

1. which data categories are actually obtainable from approved APIs or official web sources;
2. which `trading-main` `data_kind` rows should be available for task params, validation, output routing, and future storage mapping.

## Availability Rules

- Verify source availability from official documentation or source pages before implementation depends on a data category.
- Register accepted obtainable categories as `kind=data_kind` in `trading-main`.
- Keep `data_bundle` and `data_kind` separate: bundles route execution; data kinds name requested/produced data categories.
- Use one canonical source per economic measure. FRED is limited to FRED/St. Louis Fed/ALFRED-unique data or explicitly approved FRED-native research series/groups.
- Do not store provider credentials, full raw responses, or generated datasets in this repository.

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
| ThetaData | Option contracts, trades, quotes/NBBO, OHLC, EOD, open interest, implied volatility, Greeks, trade Greeks, snapshots. | `THETADATA_SECRET_ALIAS`; local terminal/runtime placement still pending. | Option Data Standard coverage needs a controlled smoke test after connector design. |
| OKX | Crypto bars; trades, quotes/tickers, and order book are available if later accepted. | Public market endpoints for market data; private endpoints need credentials. | Current accepted bundle remains bars-focused. |
| SEC EDGAR | Submissions, company facts, company concepts, frames, filing document references. | No key; identifying User-Agent and fair-access behavior required. | Use official SEC endpoints only by default. |
| ETF issuers | Holdings rows/snapshots, fund metadata, constituent weights. | Usually public web/file downloads. | No universal API; implement issuer-specific adapters and source URL/as-of tracking. |
| Federal Reserve FOMC page | Meetings, statements, minutes, SEP markers. | Public web. | No stable JSON API confirmed; preserve source URL and retrieval timestamp. |

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
