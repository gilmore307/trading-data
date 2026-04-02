# 16 Cross-Market Overlap and Session-Model Design

This document records how `trading-data` should support both a canonical shared input layer and richer session-specific downstream models.

## Core idea

The upstream data repo should expose:
- a **cross-market overlap data layer** available across both crypto and stocks
- optional additional data layers that let downstream models become richer when market-specific context is available

## Verified Alpaca overlap surface

Directly verified common data categories available from Alpaca for both stocks and crypto include:
- historical bars
- historical quotes
- historical trades
- latest bars
- latest quotes
- latest trades
- snapshots

This overlap surface should define the canonical upstream mainline contract.

## Downstream model implication

While downstream repos may define multiple model layers, the upstream implication is straightforward:

### Canonical overlap layer
This repo should make the following dependable and easy to consume:
- bars
- quotes
- trades
- snapshots
- portable derived features built from them

### Optional enhancement layers
This repo may also expose richer branches such as:
- stock-session context layers
- ETF/context layers
- options-context layers
- crypto supplemental enrichment layers

## Session-aware interpretation

Crypto is 24/7 while equities are session-bound.
The upstream data repo should support that distinction explicitly rather than pretending one timing model fits all markets.

This means the data layer should support at least these practical timing regimes:
- crypto 24h continuity
- equity extended-hours continuity where available
- equity regular-session richer context

## Extended-hours note

Direct verification in the current session showed that Alpaca stock historical bars include:
- pre-market data
- after-hours data

This means the upstream stock data layer is richer than regular-session-only bars, even though it is still not the same as a true 24/7 market.

## Practical upstream rule

Do not force the canonical contract to depend on only the richest market-specific context.
Instead:
- keep one portable overlap contract always available
- publish richer optional branches when they are available
- let downstream modeling decide when to activate the richer branches
