# 10 Role and Boundaries

`trading-data` is the code-first upstream data repository for the trading stack.

## Owns
- source adapters and acquisition logic
- fetch/build entrypoints callable by `trading-manager`
- canonical retained-artifact contracts
- artifact-readiness signals
- market-regime benchmark/context acquisition
- macro / calendar dataset acquisition

## Does not own
- cross-repo scheduling
- queue / retry / lifecycle control-plane policy
- strategy simulation
- model promotion / ranking logic
- live execution

## Stack relationship
- `trading-data` writes durable artifacts into `trading-storage`
- `trading-manager` decides when stable `trading-data` entrypoints should run
- downstream repos consume `trading-data` artifacts rather than inheriting its internals

## Mainline direction
- Alpaca is the primary market-tape source
- low-frequency macro/economic data belongs to the market-regime layer rather than symbol/month tape
- repo-local `data/` and `context/` wording is now legacy/transitional only
