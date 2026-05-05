# feature_03_strategy_selection

Legacy frozen Layer 3 feature runner.

This package implements the earlier strategy-family/variant simulation surface for the old `StrategySelectionModel` direction. Layer 3 has been reset to target state-vector construction, so this runner should not be expanded as the active Layer 3 feature boundary.

Active replacement contract:

```text
feature_03_target_state_vector
trading_data.feature_03_target_state_vector
docs/04_layer_03_target_state_vector.md
```

The legacy runner may remain available for compatibility or later downstream strategy probes, but it is no longer the source of truth for Layer 3.
