# 13 Current Input Coverage

This document records current input coverage from the perspective of the upstream `trading-data` repository.

It separates:
- implemented and verified source/data capabilities
- supported-but-not-yet-fully-hardened inputs
- missing or future-work input categories

## Verified current capabilities

### Implemented and directly verified in the current session
- OKX historical candles fetch works
- Bitget funding fetch works
- Bitget mark/index fetch works
- Bitget basis-proxy build works
- Alpaca account/paper access works
- Alpaca stock historical bars work
- Alpaca crypto historical bars work
- Alpaca stock quotes/trades/snapshots work
- Alpaca crypto quotes/trades/snapshots work
- Alpaca news works
- Alpaca options snapshots and options-contract metadata work

## Canonical mainline interpretation

From the perspective of future stock-first architecture, the most important verified canonical overlap surface is:
- bars
- quotes
- trades
- snapshots

This surface exists across both stocks and crypto in Alpaca and should shape the mainline upstream contract.

## Supplemental verified capabilities

The repo also has verified crypto supplemental-source capabilities via non-Alpaca adapters:
- OKX candles
- Bitget funding
- Bitget mark/index
- Bitget basis proxy

These are useful, but should be treated as supplemental branches when they introduce non-portable market-specific enrichments.

## Supported but not yet fully hardened

These remain relevant but are not yet the main verified canonical path:
- open interest history as a stable upstream contract
- liquidation-history archival
- order-book/depth historical archival
- broader options historical coverage beyond currently tested snapshot/metadata paths

## Current practical summary

At this stage, `trading-data` can already support:
- a canonical shared input layer based on Alpaca overlap data
- supplemental crypto enrichment acquisition paths
- downstream dataset building that distinguishes between canonical and optional inputs
