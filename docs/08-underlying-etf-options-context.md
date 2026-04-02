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

Important current direction:
- for a stock underlying, also prepare the sector ETF/context layer that represents the underlying's industry or sector environment
- prepare broad market context via major index-tracking ETFs or equivalent tradable proxies such as Nasdaq / S&P 500 / Dow / Russell 2000 related instruments
- this context layer should be available as upstream data even if the exact downstream modeling use is still under study

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

## Candidate ETF-context discovery vs relevance modeling

The upstream data layer should prepare:
- candidate ETF/context mappings
- broad-market proxy candidates
- sector/thematic ETF candidate sets for each underlying where useful
- the raw data needed to compare an underlying against those ETF candidates

However, the upstream data repo should **not** be the final owner of the ETF relevance model itself.

Recommended split:
- `trading-data` prepares the candidate context universe and the raw data inputs
- `trading-model` later evaluates which ETF/context objects are most informative for a given underlying and how they should influence decision logic

In other words:
- candidate mapping discovery belongs upstream
- relevance scoring / context-model construction belongs downstream
