# Source Availability

This file records obtainable provider/source categories for `trading-data`. It is documentation and probe evidence, not generated data and not credential material.

Purpose:

1. confirm which data categories are obtainable from approved APIs or official web/file sources;
2. guide `trading-manager` `data_kind` rows for request params, validation, routing, and storage mapping.

## Rules

- Verify availability from official documentation or source pages before implementation depends on a category.
- Use bounded probes only after documentation review.
- Keep `data_source` and `data_kind` separate: sources route execution; data kinds name requested/produced categories.
- Prefer one canonical source per economic measure. FRED is limited to FRED/St. Louis Fed/ALFRED-unique data unless an exception is reviewed.
- Do not store credentials, full raw responses, or generated datasets in this repository.
- Browser-scraped sources prefer logged-out visible pages when the accepted fields are available. Authenticated browser profiles or exported cookie jars are recovery-only surfaces, not the default data route.

## Probe CLIs

Documentation/probe inventory:

```bash
PYTHONPATH=src python3 -m feed_availability --list
PYTHONPATH=src python3 -m feed_availability --dry-run
PYTHONPATH=src python3 -m feed_availability --feed bls --feed us_treasury_fiscal_data
```

Provider/data-kind interface catalog:

```bash
PYTHONPATH=src python3 -m feed_interfaces --list
PYTHONPATH=src python3 -m feed_interfaces --feed 01_feed_alpaca_bars
PYTHONPATH=src python3 -m feed_interfaces --feed 04_feed_okx_crypto_market_data
PYTHONPATH=src python3 -m feed_interfaces --feed 08_feed_sec_company_financials
PYTHONPATH=src python3 -m feed_interfaces --feed 09_feed_thetadata_option_selection_snapshot
```

Reports write under ignored `storage/feed_availability/` or `storage/feed_interfaces/`. They may contain status, endpoint family, HTTP status, shape keys, tiny sanitized samples, row counts, and entitlement status. They must not contain credentials, request headers, or full raw payloads.

## Current Availability

| Source | Available categories | Access expectation | Current status |
|---|---|---|---|
| Alpaca | Equity bars, trades, quotes, snapshots, news. | `ALPACA_SECRET_ALIAS`; entitlement checked at runtime. | Live interface checks succeeded for bars/trades/quotes/snapshots/news. Raw trades/quotes are transient by default. |
| ThetaData | Option contracts, trades, quotes/NBBO, OHLC, EOD, open interest, IV, first-order Greeks, snapshots. | `THETADATA_SECRET_ALIAS` plus local Terminal v3 on `127.0.0.1:25503`. | Terminal-integrated; controlled live smoke succeeded. Higher-order/trade Greeks are entitlement-blocked on the current options STANDARD account. |
| OKX | Crypto bars, trades, tickers/quotes, order book. | Public market endpoints for current data; private endpoints need credentials if separately accepted. | Live interface checks succeeded for current market-data families. |
| SEC EDGAR | Submissions, company facts, company concepts, XBRL frames, filing references. | No key; identifying User-Agent and fair-access behavior required. | Live checks succeeded with bounded Apple examples; large responses require segmentation/field selection. |
| ETF issuers | Holdings rows/snapshots, weights, fund metadata. | Usually public web/file downloads. | Adapter-specific; preserve URL, as-of date, retrieval timestamp, and file/page format. |
| Trading Economics visible pages | Macro calendar/value rows visible on public recent/custom calendar pages. | No key and no authenticated cookies for the accepted current route; no historical API, download/export, WAF, or captcha bypass. | Accepted macro model-input route. Historical replay seed is complete; ongoing maintenance fetches recent/future visible calendar rows. |
| FOMC / official macro pages | Meeting calendars and release calendars. | Public official pages. | Source-of-truth rule accepted; adapter-specific. |
| FRED / ALFRED | FRED-native research series/groups and vintage views. | `FRED_SECRET_ALIAS`. | Optional reviewed research path; not a duplicate default for agency-owned measures. |
| BLS / Census / BEA / Treasury | Official agency macro/economic measures. | Public or registered aliases depending on provider. | Documentation and probes exist for optional research; not the active macro model-input route. |

## API-Level Findings

- Alpaca response shapes include bars (`t/o/h/l/c/v/vw/n`), trades (`t/p/s/x/i/c/z`), quotes (`t/bp/bs/bx/ap/as/ax/c/z`), snapshots, and news metadata.
- OKX bars are positional arrays; trades, tickers, and books are JSON objects under `data[]`.
- SEC EDGAR companyfacts can be large; production code should request only needed concepts or normalize segmented facts.
- ThetaData v3 endpoint families are available through the local Terminal; entitlement blocks are captured as evidence, not treated as parser failures.
- BLS, Census, BEA, Treasury, and FRED probes confirmed basic official API response shapes; active macro model-input work remains on the accepted visible-page route unless separately re-approved.

## Registered Data-Kind Groups

`trading-manager` owns the exact registry rows. Current groups cover:

- equity market data;
- crypto market data;
- option data;
- SEC company financial data;
- ETF holdings;
- FOMC and economic release calendars;
- macro BLS, Census, BEA, Treasury, FRED-native, and ALFRED/vintage categories.

Source-specific parameter dictionaries should be defined before a manager route depends on a category in production.

## Output Posture

- Persist final cleaned outputs or accepted SQL rows.
- Treat high-volume raw rows as transient unless an explicit debug/incident artifact is approved.
- Record sanitized request/response evidence, row counts, entitlement status, and validation outcomes in manifests or storage-owned reports.
