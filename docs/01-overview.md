# 01 Overview

`trading-data` is the canonical upstream market-data repository for the trading system.

Its job is to:
- acquire and normalize market data from supported sources
- keep high-frequency market tape stored inside this repository using manageable monthly partitions
- define the minute-level canonical retained market-data contract used downstream
- maintain low-frequency macro/economic and ETF/context artifacts as append/upsert context layers
- publish canonical cross-market and macro/context data contracts used downstream by `trading-model`
- preserve optional enrichment branches without letting them redefine the canonical main line
- expose stable fetch/build entrypoints that higher-level orchestration can call

It should not be the primary home for:
- strategy-family research
- composite construction logic
- ranking/selection logic
- live execution
- workflow sequencing and scheduler ownership
- cross-repo retry / recovery control-plane policy

## Repository relationships

Artifact chain:
- `trading-data` -> upstream data layer
- `trading-model` -> downstream research/modeling layer
- `trading-execution` -> downstream live execution layer

Control-plane relationship:
- `trading-manager` coordinates when `trading-data` entrypoints run and how cross-repo handoffs advance

## Current architectural direction

- Alpaca is the primary long-term source and current main development focus
- Alpaca overlap data across stocks and crypto defines the canonical main input surface
- OKX and Bitget are supplemental / backup sources
- crypto-only enrichments are optional, not canonical
- the data itself should live in this repo and follow monthly partition rules so GitHub remains manageable
