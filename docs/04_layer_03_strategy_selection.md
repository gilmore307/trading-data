# Layer 3 Strategy Selection

`trading-data` owns the deterministic feature-production side of Layer 3 strategy selection.

## Boundary

This layer does **not** decide which strategy variant is best, which variants should be expanded or retired, or whether a model should be promoted. Those lifecycle and oracle-review decisions belong to `trading-model` and require agent-reviewed promotion/lifecycle decisions.

`trading-data` receives manager-issued requests, runs accepted family/variant specs point-in-time against historical target bars and target-state evidence, and publishes simulation features for downstream oracle construction and model review.

## Control-plane flow

```text
trading-manager request
  -> feature_03_strategy_selection task key
  -> trading-data strategy selection feature runner
  -> trading_data.feature_03_strategy_selection
  -> trading-model oracle/lifecycle review
```

The manager request supplies the reviewed simulation window, candidate universe reference, strategy variant universe reference, output target, and run metadata. `trading-data` executes the deterministic simulation only.

## Inputs

Expected inputs are point-in-time artifacts, not future-aware labels:

- manager-issued request parameters: `start`, `end`, candidate universe reference, variant universe reference, and output root/table target;
- target-local 1-minute bars and any accepted target-state evidence;
- `market_context_state` reference from Layer 1;
- `sector_context_state` reference from Layer 2 when available;
- anonymous target candidates from the Layer 3 candidate-preparation boundary;
- reviewed strategy family/variant specs from `trading-model`.

## Output surface

Canonical feature key:

```text
feature_03_strategy_selection
```

SQL table target when promoted:

```text
trading_data.feature_03_strategy_selection
```

The feature table should represent deterministic per-bar variant behavior, such as:

- `available_time`
- `target_candidate_id`
- `3_strategy_family`
- `3_strategy_variant`
- simulation run / variant spec references
- signal state
- exposure state
- holding state
- close-to-close return contribution
- feature payload / diagnostic payload references when needed

Real ticker/company identity must remain outside model-facing fitting vectors. Routing/audit metadata may preserve symbol references separately when required.

## Non-ownership

`trading-data` does not own:

- Universal Oracle, Theoretic Strategy Oracle, or Practical Strategy Oracle construction;
- variant expansion, pruning, active-training-subset, or promotion decisions;
- StrategySelectionModel training;
- agent-review approval or rejection;
- final trade instructions, option contract selection, position size, execution, or portfolio allocation.

## Acceptance notes

Implementation is request-driven and deterministic. The current runner supports the ten active StrategySelectionModel families from serialized reviewed variant specs owned by `trading-model`: `moving_average_crossover`, `donchian_channel_breakout`, `macd_trend`, `bollinger_band_reversion`, `rsi_reversion`, `bias_reversion`, `vwap_reversion`, `range_breakout`, `opening_range_breakout`, and `volatility_breakout`. A completed run provides enough evidence for `trading-model` to compare variant paths with oracle paths and to build an agent-review package for expansion, pruning, or promotion decisions.
