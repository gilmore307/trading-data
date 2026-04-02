# 01 Overview

`trading-data` is the canonical upstream market-data repository for the trading system.

Its job is to:
- acquire and normalize market data from supported sources
- keep market data stored inside this repository using manageable monthly partitions
- define minute-level canonical raw data rules for future modeling
- publish canonical cross-market data contracts used downstream by `trading-model`
- preserve optional enrichment branches without letting them redefine the canonical main line

It should not be the primary home for:
- strategy-family research
- composite construction logic
- ranking/selection logic
- live execution

## Repository chain

- `trading-data` -> upstream data layer
- `trading-model` -> downstream research/modeling layer
- `quantitative-trading` -> downstream live execution layer

## Current architectural direction

- Alpaca is the primary long-term source and current main development focus
- Alpaca overlap data across stocks and crypto defines the canonical main input surface
- OKX and Bitget are supplemental / backup sources
- crypto-only enrichments are optional, not canonical
- the data itself should live in this repo and follow monthly partition rules so GitHub remains manageable
