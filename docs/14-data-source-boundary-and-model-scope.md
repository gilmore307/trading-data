# 14 Data Source Boundary and Model Scope

This document records a hard architectural rule for `trading-data`:

**The upstream canonical data contract must be bounded by sustainably available and cross-market-portable data.**

## Why this matters

If the upstream data repo defines a canonical contract around data that cannot be sustained or migrated into the future stock-first architecture, downstream models will inherit an architecture that cannot remain the main line.

## Current operating assumption

- future main battlefield: stocks
- crypto remains useful for data collection, experimentation, and continuity
- primary long-term paid market-data source: Alpaca
- no assumption of multiple additional premium vendors

## Core rule

When deciding whether a data family belongs in the canonical upstream contract, ask:

1. can we acquire it reliably now?
2. can we keep acquiring it sustainably later?
3. will the future stock-focused stack still have it?
4. does the future stock market have the same input or a strong equivalent?
5. does promoting this input into the canonical contract keep the downstream architecture portable?

If the answer is no, the input should not become a required canonical dependency.

## Cross-market portability rule

If a crypto-side input has no stock-side equivalent, it should not define the canonical mainline data contract.

Such inputs may still be stored and exposed as supplemental enrichment branches, but they should not reshape the main architecture.

## Canonical contract direction

The canonical upstream contract should center on Alpaca-supported overlap data such as:
- bars
- quotes
- trades
- snapshots
- and derived portable features built from them

## Supplemental contract direction

Inputs such as these remain useful but should be marked supplemental unless a future stock-portable equivalent is deliberately incorporated:
- funding
- basis/premium
- crypto-specific OI semantics
- liquidation feeds
- crypto-specific microstructure enrichments

## Planning rule

When there is a conflict between:
- a richer but non-portable data contract, and
- a slightly narrower but sustainable portable contract,

prefer keeping the sustainable portable contract as canonical.
