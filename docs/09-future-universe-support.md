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

## Current etf.com discovery note

`etf.com` is a potentially useful source for discovering ETF candidates, but direct HTTP requests from this environment are currently blocked by Cloudflare.

That means:
- do not treat `etf.com` as a simple automation-ready canonical source yet
- keep it in mind as a possible manual or browser-assisted discovery source
- prefer storing final approved candidate mappings inside the repo rather than depending on the live website at runtime
