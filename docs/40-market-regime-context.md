# 40 Market-Regime Context

This document groups the market-regime context layer used by `trading-data`.

## Layer types
- macro / economic datasets
- official calendars and release artifacts
- ETF / proxy benchmark instruments
- options-context enrichment inputs

## Macro/economic storage rule
Use canonical permanent files under `trading-storage/1_market_regime/1_permanent/`.

Examples:
- `1_macro/fred/<series>.jsonl`
- `1_macro/bls/<series>.jsonl`
- `1_macro/bea/<series>.jsonl`
- `1_macro/census/<dataset>.jsonl`
- `1_macro/treasury/<dataset>.jsonl`
- `7_events_and_calendars/*.jsonl`

## ETF/proxy rule
ETF and proxy instruments are retained primarily as market-regime/context instruments.

Current interpretation:
- broad-beta ETFs
- rates/credit/fx/metals proxies
- sector rotation ETFs
- selected industry/thematic ETFs
- crypto proxy ETFs

These are bar/context-first instruments, not a separate orchestration layer.

## ETF holdings / look-through rule
The active mainline does **not** depend on constituent-level ETF look-through.
ETF proxies remain useful through their own retained bar/context behavior.

## Economic-event schema rule
Model scheduled economic events in two layers:
1. calendar / expectation layer
2. release result / actual layer

This keeps scheduling semantics separate from realized-event analysis semantics.
