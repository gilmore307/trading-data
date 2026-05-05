# source_03_strategy_selection

Legacy compatibility source for Layer 3 target-local bars/liquidity.

This source was named for the earlier `StrategySelectionModel` boundary. Layer 3 has been reset to target state-vector construction. New contracts should use target-state names such as:

```text
source_03_target_state
feature_03_target_state_vector
```

During migration, this source may still provide candidate-symbol 1Min bars and liquidity evidence, but it should be treated as a compatibility path rather than the active naming authority.
