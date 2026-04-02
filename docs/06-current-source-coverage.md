# 06 Current Source Coverage

This document records current source/data coverage from the perspective of `trading-data`.

## Verified Alpaca capabilities

Directly verified in the current session:
- stock historical bars
- stock historical quotes
- stock historical trades
- stock latest bars / quotes / trades
- stock snapshots
- stock extended-hours historical bars
- crypto historical bars
- crypto historical quotes
- crypto historical trades
- crypto latest bars / quotes / trades
- crypto snapshots
- crypto latest orderbooks
- news
- options snapshots
- options contract metadata including open interest
- options latest quote / trade
- paper/account access

## Verified supplemental-source capabilities

Also directly verified in the current session:
- OKX historical candles fetch
- Bitget funding fetch
- Bitget mark/index fetch
- Bitget basis-proxy build

## Current interpretation

- Alpaca now defines the mainline source coverage story
- OKX and Bitget remain useful supplemental / backup capabilities
- broader optional enrichment coverage can be kept, but should not replace the canonical overlap contract
