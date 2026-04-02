# 17 Future Research Universe Selection

This document records the upstream data-repo view of future research-universe selection.

The point of including it here is to clarify what kinds of symbols the upstream data layer should prioritize for canonical support.

## Core principle

The upstream repo should prioritize symbols that support the intended long-term architecture well.
That means symbols with strong support for:
- underlying data
- ETF/context relationships
- options-context availability
- sustainable Alpaca coverage

## Upstream implication

The data repo does not decide the final research/trading universe on its own, but it should prioritize support for symbols that are strong future mainline candidates.

## High-priority candidate classes for upstream support

### 1. Core broad-market ETFs
Important because they help define market-state and context layers.

### 2. Sector ETFs
Important for relative-strength and regime-context work.

### 3. High-liquidity large-cap stocks
Important because they are strong candidates for the primary underlying universe.

### 4. Thematic / cross-asset proxies
Examples include BTC-related ETFs and other symbols that bridge broader themes into the stock-first architecture.

## Supporting-data rule

The upstream data layer should especially prioritize symbols that have:
- stable bars/quotes/trades/snapshots coverage
- useful ETF/context interpretation
- useful options-context availability
- sufficient liquidity and continuity to avoid fragile downstream use

## Non-goal

The upstream repo should not chase maximum symbol count for its own sake.
The goal is to support the symbols that best fit the future sustainable architecture.
