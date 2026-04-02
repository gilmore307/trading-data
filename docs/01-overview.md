# 01 Overview

`trading-data` is the canonical upstream market-data repository for the trading system.

Its job is to:
- acquire and normalize market data from supported sources
- define and enforce raw/intermediate/derived data contracts
- maintain sustainable data-boundary rules for future modeling
- build canonical Alpaca-centered cross-market input layers used downstream by modeling repos
- preserve optional enrichment-data branches without letting them redefine the canonical main line

It should **not** be the primary home for strategy-family research, composite construction, ranking/selection logic, or live execution.
Those responsibilities belong downstream.

## Upstream / downstream split

### Upstream: `trading-data`
Owns:
- source adapters and data-maintenance code under `src/`
- raw data acquisition and partitioning
- Alpaca-centered cross-market overlap data contracts
- canonical sustainable input design
- optional enrichment data boundaries
- dataset foundation work for downstream modeling

### Midstream: `trading-model`
Owns:
- strategy/model research
- family/variant research
- regime/composite modeling
- ranking/selection logic
- promotion-candidate generation

### Downstream: `quantitative-trading`
Owns:
- live trade daemon
- realtime execution
- active strategy consumption
- execution artifacts and production runtime behavior

## Repository direction

This repo was split out as the new upstream data layer so the system can stop mixing data acquisition responsibilities into the modeling repo.

The current direction is:
- make `trading-data` the canonical home for market-data acquisition and contracts
- treat Alpaca as the primary long-term source and current main development focus for the future stock-first main line
- define one canonical Alpaca-centered cross-market overlap layer shared by crypto and stocks
- downgrade OKX/Bitget to supplemental or backup source roles unless a specific enrichment use justifies them
- keep crypto-only enrichments available as supplemental branches rather than canonical dependencies
- keep project docs current as the split hardens

## Main working areas

- `docs/` — project documentation and data-boundary definitions
- `src/` — source adapters, fetch/update jobs, and data-maintenance entrypoints
- `config/` — source/data pipeline configuration
- `data/` — canonical raw/intermediate/derived/report/manifests structure as this repo matures

## Current cleanup goals

1. establish `trading-data` as the canonical upstream data repository
2. rewrite inherited docs so they reflect pure data-layer scope
3. move acquisition scripts and data-policy docs out of downstream repos
4. define Alpaca-centered cross-market canonical input design
5. preserve supplemental crypto enrichments without letting them define the mainline architecture
