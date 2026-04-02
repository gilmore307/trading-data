# 08 Underlying ETF Options Context

This document records how the upstream data layer should think about object layers for future stock-first modeling.

## Core principle

The primary downstream research/trading object is the underlying.
Options are not required to be the immediate main trading object; they are primarily valuable as a context/signal-enrichment layer.

## Main object layers

### 1. Underlying layer
Examples:
- stocks
- ETFs
- BTC-related ETFs and other equity-market proxies

### 2. ETF/context layer
Examples:
- broad-market ETFs
- sector ETFs
- thematic ETFs
- cross-asset proxy ETFs

### 3. Options-context layer
Examples:
- option contract metadata
- open interest
- option volume
- option quotes
- option trades
- option snapshots
- strike / expiry structure

## Upstream implication

The data repo should prioritize support for symbols that can participate in a richer multi-layer structure:
- underlying data
- ETF/context support
- options-context support
