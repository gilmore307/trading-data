# feature_03_strategy_selection

Deterministic Layer 3 strategy selection feature surface.

## Boundary

This package executes reviewed strategy family/variant specs against point-in-time target bars and target-state evidence after a `trading-manager` request. It produces simulation features for `trading-model` oracle construction and lifecycle review.

It does not decide which variant is best, expand/prune variants, train StrategySelectionModel, or approve promotion. Those decisions belong to `trading-model` review scripts and agent-reviewed lifecycle decisions.

## Request flow

```text
trading-manager task/request
  -> trading-data feature_03_strategy_selection runner
  -> trading_data.feature_03_strategy_selection
  -> trading-model oracle/lifecycle review
```

## Expected inputs

- manager-issued `start` / `end` window;
- anonymous target candidate universe reference;
- reviewed strategy variant universe reference;
- target-local 1-minute bars and accepted target-state evidence;
- Layer 1 market context and Layer 2 sector context references when available.

## Expected output

One deterministic point-in-time feature surface keyed by `run_id`, `available_time`, `target_candidate_id`, `3_strategy_family`, and `3_strategy_variant`.

The output contains signal/exposure/holding/return-path evidence for `trading-model` to build Universal Oracle, Theoretic Strategy Oracle, Practical Strategy Oracle, expansion/pruning proposals, and promotion evidence.

## Current implementation

The runner supports the ten active StrategySelectionModel families from serialized variant specs owned by `trading-model`: `moving_average_crossover`, `donchian_channel_breakout`, `macd_trend`, `bollinger_band_reversion`, `rsi_reversion`, `bias_reversion`, `vwap_reversion`, `range_breakout`, `opening_range_breakout`, and `volatility_breakout`. It reads source bars from `source_03_strategy_selection`, maps routing symbols to `target_candidate_id` through the manager-supplied target-candidate rows, writes `trading_data.feature_03_strategy_selection`, and keeps ticker/company identity out of emitted feature rows.

CLI entrypoint:

```bash
trading-data-feature-03-strategy-selection --request-json request.json
```

Compatibility wrapper:

```bash
PYTHONPATH=src python3 scripts/generate_feature_03_strategy_selection.py --request-json request.json
```
