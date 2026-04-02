# 03 Data Policy and Contracts

This document consolidates the core storage, source-priority, and canonical contract rules for `trading-data`.

## Source priority

### Primary source
Alpaca is the primary long-term source and current architectural main focus.

Reason:
- future main battlefield is stocks
- Alpaca supports stocks, ETFs, options context, news, and crypto overlap data
- Alpaca provides the cross-market overlap surface that should define the canonical mainline input layer

### Supplemental / backup sources
#### OKX
Use as:
- supplemental crypto source
- backup candles source
- reference source when needed

#### Bitget
Use as:
- supplemental crypto enrichment source
- backup/reference source
- provider of optional derivatives-specific context when useful

## Canonical-vs-supplemental rule

- Alpaca-supported cross-market overlap data should shape the canonical contract
- OKX/Bitget data should not redefine the mainline architecture unless there is a specific reason and a stock-portable equivalent story
- crypto-only enrichments remain optional/supplemental

## Storage rule

Market data should be stored in this repository and partitioned by symbol and month.

Canonical market-tape path:
- `data/<symbol>/<YYMM>/<dataset>.jsonl`

Examples:
- `data/AAPL/2604/bars_1min.jsonl`
- `data/BTC-USD/2603/bars_1min.jsonl`
- `data/AAPL/2604/quotes.jsonl`
- `data/AAPL/2604/trades.jsonl`

Symbol-format note:
- Alpaca crypto API requests use slash form such as `BTC/USD`
- on-disk path normalization should still use a safe symbol directory such as `BTC-USD`

Keep `data/` focused on actual market dataset files only.

## Canonical raw granularity rule

The canonical raw market-data layer should be minute-level across all supported asset classes.

That means:
- minute-level bars are the canonical raw bar layer
- higher timeframes are derived/aggregated layers

## Canonical overlap surface

The canonical mainline input surface should be defined by data that Alpaca supports across both stocks and crypto.

Directly verified common categories include:
- historical bars
- historical quotes
- historical trades
- latest bars
- latest quotes
- latest trades
- snapshots

## Canonical raw bar rule

Canonical raw bars should be minute-level.

Main raw bar object:
- `bars_1min.jsonl`

## Canonical derived features

The canonical mainline feature families should primarily derive from the overlap surface, such as:
- returns
- volatility
- range/structure
- volume
- trade count
- VWAP-relative structure
- quote spread / mid / quote-derived imbalance proxies
- trade activity intensity
- session / calendar context

## Optional enrichment contract

Data families without strong stock-portable equivalents remain optional/supplemental, such as:
- funding
- basis/premium
- crypto-specific OI semantics
- liquidation feeds
- crypto-specific orderbook enrichments
