# m03_target_state_vector_feature_generation

Deterministic Layer 3 target state-vector feature production.

This package builds point-in-time feature rows for `TargetStateVectorModel`; it must not simulate downstream action variants or make model promotion decisions.

## Intended table

```text
trading_data.m03_target_state_vector_feature_generation
```

## V1 feature blocks

The feature surface should expose the same four model-facing blocks used by `trading-model`. Market, sector, target, and cross-state blocks must declare identical `state_observation_windows` on every row:

- `market_state_features`
- `sector_state_features`
- `target_state_features`
- `cross_state_features`

The first implementation stores these as Python dictionaries and `sql.py` persists them as JSONB blocks. Block names remain inspectable in output rows and receipts.

## Current implementation

`generator.py` consumes candidate-mapped target-local bars plus optional point-in-time market/sector context rows and emits one row per `target_candidate_id + available_time` with the four V1 blocks. `sql.py` reads accepted `m03_target_state_vector_data_acquisition` rows and writes `trading_data.m03_target_state_vector_feature_generation` keyed by `target_candidate_id + available_time + target_context_state_version`.

V1 sparse synchronized state windows:

```text
10min, 1h, 1D, 1W
```

These are state observation windows, not downstream action variants. They are synchronized across market, sector, target, and cross-state blocks.

Each block also exposes a `multi_frame_state` map keyed by the same windows. The map is the canonical feature route for Layer 3 state fitting:

- market/sector frames project point-in-time context return, direction, volatility, trend quality, and liquidity/tradability values when supplied by upstream rows;
- target frames derive completed-bar return, volatility/range, volume, trend quality, path stability, persistence, and late-trend risk from target-local source rows;
- cross-state frames compare target return/volatility against market and sector context for the matching window, falling back to the 15-minute frame only for legacy scalar compatibility.

## Required row keys

- `available_time`
- `tradeable_time`
- `target_candidate_id`
- `market_context_state_ref`
- `sector_context_state_ref`
- `target_context_state_version`
- `source_run_ref`

## Non-ownership

This package does not own target-state labels, model training, state clustering, promotion decisions, downstream action selection, option contracts, position sizing, execution, or portfolio allocation.
