# 03 Source Priority and Scope

This document defines current source priority for `trading-data`.

## Primary source

### Alpaca
Alpaca is the primary long-term source and the current architectural main focus.

Reason:
- future main battlefield is stocks
- Alpaca supports stocks, ETFs, options context, news, and crypto overlap data
- Alpaca provides the cross-market overlap surface that should define the canonical mainline input layer

## Supplemental / backup sources

### OKX
Use as:
- supplemental crypto source
- backup candles source
- reference source when needed

### Bitget
Use as:
- supplemental crypto enrichment source
- backup/reference source
- provider of optional derivatives-specific context when useful

## Canonical-vs-supplemental rule

- Alpaca-supported cross-market overlap data should shape the canonical contract
- OKX/Bitget data should not redefine the mainline architecture unless there is a specific reason and a stock-portable equivalent story
- crypto-only enrichments remain optional/supplemental
