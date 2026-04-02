# 05 Canonical Data Contract

This document defines the intended canonical input contract for downstream modeling.

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

Data families without strong stock-portable equivalents should remain optional/supplemental, such as:
- funding
- basis/premium
- crypto-specific OI semantics
- liquidation feeds
- crypto-specific orderbook enrichments

These may be published by this repo, but they should not define the only workable downstream model path.
