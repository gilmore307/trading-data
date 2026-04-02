# 09 Future Universe Support

This document records the upstream data-repo view of future universe support.

## Priority universe classes

The upstream repo should especially prioritize support for:
- core broad-market ETFs
- sector ETFs
- high-liquidity large-cap stocks
- thematic / cross-asset proxies such as BTC-related ETFs

## Current data-preparation implication

Even before downstream model construction is finalized, the data layer should be ready to provide:
- the underlying itself
- the underlying's sector/industry ETF context where applicable
- broad market context via major index-tracking proxies (for example Nasdaq, S&P 500, Dow, Russell 2000 related ETFs/proxies)
- candidate ETF sets that may later be evaluated for relevance against the underlying

Exactly how these context layers participate in modeling can remain a downstream research question.
Preparing the data coverage for them is already an upstream data task.

## Support rule

The most important symbols are those that have:
- stable Alpaca bars/quotes/trades/snapshots coverage
- useful ETF/context relationships
- useful options-context availability
- sufficient liquidity and continuity

## Non-goal

The upstream data repo should not chase maximum symbol count.
The goal is to support the symbols that best fit the future sustainable stock-first architecture.
