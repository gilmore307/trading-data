# 07 Cross-Market Overlap

This document records the canonical overlap layer between stocks and crypto.

## Core overlap categories

The directly verified Alpaca overlap layer includes:
- bars
- quotes
- trades
- snapshots

This overlap surface should be the mainline upstream contract.

## Why this matters

This overlap layer makes it possible for downstream repos to maintain:
- a portable cross-market model path
- a crypto-capable 24h model path
- a stock-capable model path
- a stable baseline that survives future stock-first expansion

## Session interpretation

Crypto is 24/7.
Equities are session-bound but Alpaca also provides extended-hours bars.

Therefore the upstream data repo should support:
- crypto 24h continuity
- equity extended-hours continuity
- equity regular-session richer context layers

## Upstream rule

Do not force the canonical upstream contract to depend on only the richest market-specific context.
Instead:
- keep the overlap layer stable and always available
- expose richer optional layers separately
- let downstream models decide when to activate the richer layers
