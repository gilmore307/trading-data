# 12 SEC N-PORT Holdings Research

This document records the current understanding of SEC Form N-PORT as a candidate authoritative source path for ETF/fund holdings context.

## Why this matters

Current lighter-weight paths for ETF holdings are blocked or incomplete in this environment:
- `etf.com` direct HTTP fetch is blocked by Cloudflare
- `etfdb.com` direct HTTP fetch is blocked by Cloudflare
- Finnhub `/etf/holdings` is not accessible with the currently tested account permissions
- Alpaca has not been validated as a direct ETF holdings source

Because of that, SEC/N-PORT is worth tracking as a more serious candidate path.

## Current understanding

Based on public SEC search results and publicly visible descriptions:
- SEC publishes Form N-PORT data sets
- the data appears to be distributed in bulk/packaged form rather than as a lightweight symbol-level holdings API
- the data path appears more authoritative but also heavier to ingest

## Known relevant artifacts

Publicly discoverable items include:
- Form N-PORT Data Sets page
- `nport_readme.pdf`
- quarterly dataset packages such as `2023q1_nport.zip`

## Known relevant table/object names from public search snippets

The following table/object names appear relevant:

### `FUND_REPORTED_HOLDING`
This appears to contain the fund's reported holdings.
This is likely the central holdings table for our use case.

### `IDENTIFIERS`
This appears to contain other identifiers for each holding.
This may help map holdings to stable constituent symbols or related identifiers if needed.

### `FUND_VAR_INFO`
This appears to contain fund-level variable information, including designated index information.
This may help interpret broad/sector/index relationships.

## Current likely fit for our use case

N-PORT looks more suitable for:
- authoritative ETF/fund holdings ingestion
- monthly/periodic holdings context refresh
- later normalization into our compact ETF holdings schema

It does **not** currently look like a lightweight path for:
- rapid symbol-level queries on demand
- simple low-complexity per-request holdings lookup

## Intended normalized output

Even if SEC/N-PORT is the upstream raw source, the normalized data retained by `trading-data` should stay compact.

Current intended normalized schema remains:
- `etf_symbol`
- `as_of_date`
- `constituent_symbol`
- `constituent_name`
- `weight_percent`

## Current status

SEC/N-PORT is now treated as:
- a candidate authoritative source path for ETF holdings
- not yet an operationally ingested path in this repo
- worthy of dedicated schema/ingestion research before implementation

## Next research questions

1. how to map ETF ticker symbols to the relevant fund/series/entity identifiers in N-PORT
2. how often the data is available and what lag to expect
3. which exact files/tables are required to reconstruct the compact holdings schema
4. how much raw source material needs to be retained versus normalized-and-discarded
5. whether the ingestion path should keep only the compact normalized output in-repo after parsing
