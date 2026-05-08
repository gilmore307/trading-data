# Layer 3 Target State Vector

`trading-data` owns the deterministic data-production side of Layer 3 target state-vector construction. The source/feature surface is implemented; promotion remains gated by model-side real-data evidence.

Layer 3 is target state-vector production. Action/variant simulation code is not part of the active Layer 3 contract.

## Boundary

`trading-data` receives manager-issued requests, reads point-in-time source evidence, and publishes deterministic target-state feature surfaces for `trading-model` to train and evaluate `TargetStateVectorModel`.

`trading-data` does **not** decide whether a target should be traded, which downstream action/expression to use, whether a model should be promoted, or whether a state relationship is accepted. Those modeling and review decisions belong to `trading-model` and the `trading-manager` control plane.

## Control-plane flow

```text
trading-manager request
  -> feature_03_target_state_vector task key
  -> trading-data target state-vector feature runner
  -> trading_data.feature_03_target_state_vector
  -> trading-model TargetStateVectorModel training/evaluation/review
```

Active contracts use target-state names:

```text
source_03_target_state
feature_03_target_state_vector
```

Current implementation:

- `src/data_source/source_03_target_state/` normalizes caller-supplied point-in-time target-local bars and liquidity/quote evidence into `trading_data.source_03_target_state` rows keyed by `target_candidate_id + timeframe + timestamp`.
- `src/data_feature/feature_03_target_state_vector/generator.py` builds deterministic market/sector/target/cross-state feature blocks.
- `src/data_feature/feature_03_target_state_vector/sql.py` reads `source_03_target_state` plus optional Layer 1/2 context rows and writes `trading_data.feature_03_target_state_vector` with JSONB blocks.
- CLI entrypoints are registered for `trading-data-source-03-target-state` and `trading-data-feature-03-target-state-vector`.

## Inputs

Expected inputs are point-in-time artifacts, not future-aware labels:

- manager-issued request parameters: `start`, `end`, candidate universe reference, Layer 1/2 state references, output target, and run metadata;
- anonymous target candidate rows from the Layer 3 candidate-preparation boundary;
- target-local 1-minute bars;
- target liquidity, quote/trade, spread, and dollar-volume evidence when available;
- `market_context_state` reference from Layer 1;
- `sector_context_state` reference from Layer 2;
- optional accepted event/risk availability flags when they are point-in-time.

## Output surface

Canonical feature key:

```text
feature_03_target_state_vector
```

SQL table target when promoted:

```text
trading_data.feature_03_target_state_vector
```

The feature table should expose decomposable blocks:

- `available_time`
- `tradeable_time`
- `target_candidate_id`
- `market_context_state_ref`
- `sector_context_state_ref`
- `market_state_features` payload or columns
- `sector_state_features` payload or columns
- `target_state_features` payload or columns
- `cross_state_features` payload or columns
- feature-quality diagnostics
- source/run references

Real ticker/company identity must remain outside model-facing feature vectors. `source_03_target_state.symbol` is source/audit/routing metadata only; `feature_03_target_state_vector` feature blocks must use `target_candidate_id` and context refs rather than ticker/company identity.

## Non-ownership

`trading-data` does not own:

- target-state label design beyond deterministic label-materialization requests accepted by `trading-model`;
- model training, state clustering, embeddings, promotion decisions, or agent review;
- downstream action/variant lifecycle;
- final trade instructions, option contract selection, position size, execution, or portfolio allocation.

## Acceptance notes

A completed feature run should let `trading-model` compare:

1. market-only baseline;
2. market + sector baseline;
3. market + sector + target state vector.

The output is accepted only if it is point-in-time, identity-safe, reproducible from manager request metadata, and split into inspectable market/sector/target/cross-state blocks.


## V1 state windows

The first target-state feature contract should use sparse synchronized state windows rather than action-like parameter grids:

```text
5min, 15min, 60min, 390min
```

These windows are for trailing return, volatility, volume, liquidity, and relative-strength state summaries. They are not downstream action variants and should not create a variant universe.
