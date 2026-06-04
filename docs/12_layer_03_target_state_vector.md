# Layer 03 - Target State Vector Data

`trading-data` owns the deterministic data-production side of Layer 3 target state-vector construction. The source/feature surface is implemented; promotion remains gated by model-side real-data evidence.

Layer 3 is target state-vector production. Action/variant simulation code is not part of the active Layer 3 contract.

## Boundary

`trading-data` receives manager-issued requests, reads point-in-time source evidence, and publishes deterministic target-state feature surfaces for `trading-model` to train and evaluate `TargetStateVectorModel`.

`trading-data` does **not** decide whether a target should be traded, which downstream action/expression to use, whether a model should be promoted, or whether a state relationship is accepted. Those modeling and review decisions belong to `trading-model` and the `trading-manager` control plane.

## Control-plane flow

```text
trading-manager request
  -> m03_target_state_vector_feature_generation task key
  -> trading-data target state-vector feature runner
  -> trading_data.m03_target_state_vector_feature_generation
  -> trading-model TargetStateVectorModel training/evaluation/review
```

Active contracts use target-state names. Layer 3 consumes reviewed candidate-symbol evidence plus Layer 1/2 context references:

```text
m03_target_state_vector_data_acquisition
m03_target_state_vector_feature_generation
```

Current implementation:

- Live Layer 3 receives candidate symbols from the reviewed realtime total-symbol pool and target metadata; historical replay receives them from its frozen point-in-time candidate universe. ETF holdings do not define the ordinary candidate universe.
- `src/data_source/m03_target_state_vector_data_acquisition/` normalizes caller-supplied point-in-time target-local bars and liquidity/quote evidence into `trading_data.m03_target_state_vector_data_acquisition` rows keyed by `target_candidate_id + timeframe + timestamp`.
- `src/data_feature/m03_target_state_vector_feature_generation/generator.py` builds deterministic market/sector/target/cross-state feature blocks.
- `src/data_feature/m03_target_state_vector_feature_generation/sql.py` reads `m03_target_state_vector_data_acquisition` plus optional Layer 1/2 context rows and writes `trading_data.m03_target_state_vector_feature_generation` with JSONB blocks.
- CLI entrypoints are registered for `trading-data-m03-target-state-vector-data-acquisition` and `trading-data-m03-target-state-vector-feature-generation`.

## Inputs

Expected inputs are point-in-time artifacts, not future-aware labels:

- manager-issued request parameters: `start`, `end`, candidate universe reference, Layer 1/2 state references, output target, and run metadata;
- reviewed live realtime-pool candidate rows or frozen historical point-in-time candidate rows, plus target metadata;
- target-local 1-minute bars;
- target liquidity, quote/trade, spread, and dollar-volume evidence when available;
- `market_context_state` reference from Layer 1;
- `sector_context_state` reference from Layer 2;
- optional accepted event/risk availability flags when they are point-in-time.

## Output surface

Canonical feature key:

```text
m03_target_state_vector_feature_generation
```

SQL table target when promoted:

```text
trading_data.m03_target_state_vector_feature_generation
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

Real ticker/company identity must remain outside model-facing feature vectors. `m03_target_state_vector_data_acquisition.symbol` is source/audit/routing metadata only; `m03_target_state_vector_feature_generation` feature blocks must use `target_candidate_id` and context refs rather than ticker/company identity.

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
10min, 1h, 1D, 1W
```

These windows are for trailing return, volatility, volume, liquidity, and relative-strength state summaries. They are not downstream action variants and should not create a variant universe.

Each market, sector, target, and cross-state block should expose a `multi_frame_state` map keyed by those same windows. Target frames are derived from completed 1-minute source bars; market/sector frames project point-in-time upstream context; cross-state frames compare target behavior against market and sector behavior at the matching frame. The 15-minute scalar fields may remain for compatibility, but model training should consume the explicit multi-frame map.
