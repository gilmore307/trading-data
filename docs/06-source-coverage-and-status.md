# 06 Source Coverage and Status

This document consolidates current source coverage and operational status.

## Alpaca verified capabilities

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

## Supplemental-source verified capabilities

Also directly verified:
- OKX historical candles fetch
- Bitget funding fetch
- Bitget mark/index fetch
- Bitget basis-proxy build

## Operational-path view

### Operational now
- Alpaca market-tape overlap path
- Alpaca news/options-context path
- OKX supplemental candles path
- Bitget supplemental enrichment path

### Candidate but not operational now
- `etf.com` candidate ETF discovery path (blocked by Cloudflare for direct HTTP use)
- `etfdb.com` candidate ETF discovery path (blocked by Cloudflare for direct HTTP use)
- Finnhub ETF holdings path (blocked by current account access)
- SEC/N-PORT holdings path (promising but not yet ingested)

## Current interpretation

- Alpaca defines the mainline market-data source story
- OKX and Bitget remain useful supplemental / backup capabilities
- ETF holdings still require a separate authoritative or workable operational path
