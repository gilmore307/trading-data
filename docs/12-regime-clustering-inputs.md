# 12 Regime Clustering Inputs

This document records the input framework that `trading-data` should support for unsupervised regime / market-state modeling downstream.

The purpose here is not to define the downstream model itself, but to define the data-layer input surface the upstream data repo should make possible.

## Why this belongs in `trading-data`

`trading-data` owns the upstream input contract.
That means this repo should make clear:
- which raw inputs exist
- which derived inputs can be built internally from canonical data
- which enrichments require external/supplemental handling
- which inputs are canonical vs optional

## Current modeling direction downstream

The current downstream regime path is unsupervised clustering.

That implies this repo should emphasize:
- stable market-state feature inputs
- reproducible source-aligned datasets
- explicit separation between canonical and optional enrichments

## Input layers the data repo should support

### Layer 1 — raw market data
Examples:
- OHLCV / bars
- quotes
- trades
- source snapshots

### Layer 2 — internally generated derived features
Examples:
- returns over multiple windows
- realized volatility / rolling volatility
- range / ATR-like features
- trend slope / persistence features
- breakout distance / range-location features
- compression / expansion features
- volume / trade-count relative features
- VWAP-relative features

### Layer 3 — optional external or market-specific enrichments
Examples:
- funding rate history
- basis / premium history
- open interest history
- liquidation feeds
- order-book/depth enrichments

### Layer 4 — downstream evaluation-aligned data products
Examples:
- market-state snapshot tables
- aligned candidate/variant comparison datasets
- cluster-evaluation support tables

## Canonical data-boundary rule

The mainline input contract should be shaped by data that is:
- sustainable
- portable into the future stock-first architecture
- obtainable from the long-term primary source stack

At the current planning stage, this means Alpaca-compatible overlap data should dominate the canonical contract.

## Optional-enrichment rule

Crypto-only or non-portable enrichments may still be stored or published by this repo, but they should be clearly marked as supplemental rather than canonical.

## Immediate implication for this repo

`trading-data` should focus on making the following dependable:
- canonical shared bars/quotes/trades/snapshots inputs
- reproducible derived feature-ready datasets
- explicit supplemental enrichment branches for non-canonical data
