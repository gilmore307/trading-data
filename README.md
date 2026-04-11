# trading-data

`trading-data` is the code-first upstream data repository for the trading stack.
It owns source adapters, fetch/build entrypoints, canonical data contracts, and artifact-readiness signals.
It does **not** own cross-repo orchestration policy.

## Role in the stack

```mermaid
flowchart LR
    TD[trading-data] --> TS[trading-strategy]
    TD --> TM[trading-model]
    MG[trading-manager] -.orchestrates.-> TD
    TD -.writes artifacts.-> ST[(trading-storage)]
```

## Owns
- market-data acquisition and normalization
- source-specific adapters under `src/`
- stable manager-facing fetch/build entrypoints
- canonical retained-artifact contracts
- artifact-readiness signal emission
- market-regime benchmark/context data acquisition
- macro / calendar dataset acquisition

## Does not own
- scheduling / queue policy
- cross-repo workflow sequencing
- control-plane retry / lifecycle policy
- strategy simulation
- model ranking / promotion policy
- live execution

## Canonical inputs
- external data-source responses (Alpaca primary; other sources optional)
- repo config under `config/`
- source credentials via local environment

## Canonical outputs
- market-tape artifacts under `trading-storage/2_market_tape/`
- market-regime artifacts under `trading-storage/1_market_regime/`
- readiness signals under `trading-storage/1_market_regime/3_credentials/<group_name>/<symbol>/`

## Current mainline contract
- Alpaca is the primary source for retained market-tape data
- retained market-tape partitions are symbol/month scoped
- canonical retained tape datasets are minute-level by default:
  - `bars_1min.jsonl`
  - `quotes_1min.jsonl`
  - `trades_1min.jsonl`
- low-frequency macro/economic datasets remain append/upsert context artifacts rather than symbol/month tape
- benchmark ETFs/proxies are part of the market-regime layer, not a separate orchestration system
- `trading-storage` is now the canonical durable destination; repo-local `data/` wording is legacy only

## Current status
- storage write paths have been repathed to `trading-storage`
- signal output has been repathed to `trading-storage/1_market_regime/3_credentials/<group_name>/<symbol>/`
- compaction / normalize tools now target `trading-storage` instead of repo-local `data/`
- remaining work is mostly contract cleanup and validation rather than topology redesign

## Read in order
1. `docs/README.md`
2. `docs/10-role-and-boundaries.md`
3. `docs/20-artifact-contracts.md`
4. `docs/30-entrypoints-and-signals.md`
5. `docs/40-market-regime-context.md`
6. `docs/50-status-and-open-questions.md`

## Next work
See `TODO.md`.

Current next-mile work is now mostly broader operational validation and a few remaining path/edge-case cleanups rather than contract ambiguity.
