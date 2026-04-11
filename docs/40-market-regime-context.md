# 40 Market-Regime Context

This document groups the market-regime context layer used by `trading-data`.

## Layer types
- macro / economic datasets
- official calendars and release artifacts
- ETF / proxy benchmark instruments
- options-context enrichment inputs

## Macro/economic storage rule
Use canonical regime data files under `trading-storage/1_market_regime/1_data/`.

Examples:
- `macro/fred/<series>.jsonl`
- `macro/bls/<series>.jsonl`
- `macro/bea/<series>.jsonl`
- `macro/census/<dataset>.jsonl`
- `macro/treasury/<dataset>.jsonl`
- `official_calendar/<entity_id>/*.jsonl`

## ETF/proxy rule
ETF and proxy instruments are retained primarily as market-regime/context instruments.

Current interpretation:
- broad market-state ETFs
- rates/credit/fx/metals proxies
- sector rotation ETFs
- selected industry/thematic ETFs
- crypto proxy ETFs

These are bar/context-first instruments, not a separate orchestration layer.

Current storage rule:
- regime ETF/proxy data belongs under `trading-storage/1_market_regime/1_data/etf/<group_name>/<SYMBOL>/...`
- `group_name` must come from `market_regime_summary.csv`
- old taxonomy folders are not the mainline contract

## ETF holdings / look-through rule
The active mainline does **not** depend on constituent-level ETF look-through.
ETF proxies remain useful through their own retained bar/context behavior.

## Economic-event schema rule
Model scheduled economic events in two layers:
1. calendar / expectation layer
2. release result / actual layer

This keeps scheduling semantics separate from realized-event analysis semantics.
