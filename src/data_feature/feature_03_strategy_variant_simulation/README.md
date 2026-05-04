# feature_03_strategy_variant_simulation

Deterministic Layer 3 strategy variant simulation feature surface.

## Boundary

This package will execute reviewed strategy family/variant specs against point-in-time target bars and target-state evidence after a `trading-manager` request. It produces simulation features for `trading-model` oracle construction and lifecycle review.

It does not decide which variant is best, expand/prune variants, train StrategySelectionModel, or approve promotion. Those decisions belong to `trading-model` review scripts and agent-reviewed lifecycle decisions.

## Request flow

```text
trading-manager task/request
  -> trading-data feature_03_strategy_variant_simulation runner
  -> trading_data.feature_03_strategy_variant_simulation
  -> trading-model oracle/lifecycle review
```

## Expected inputs

- manager-issued `start` / `end` window;
- anonymous target candidate universe reference;
- reviewed strategy variant universe reference;
- target-local 1-minute bars and accepted target-state evidence;
- Layer 1 market context and Layer 2 sector context references when available.

## Expected output

One deterministic point-in-time feature surface keyed by simulation run, available time, anonymous target candidate, strategy family, and strategy variant.

The output contains signal/exposure/holding/return-path evidence for `trading-model` to build Universal Oracle, Theoretic Strategy Oracle, Practical Strategy Oracle, expansion/pruning proposals, and promotion evidence.

## Current implementation

The first runner supports the accepted `moving_average_crossover` baseline family from serialized variant specs. It reads source bars from `source_03_strategy_selection`, maps routing symbols to `target_candidate_id` through the manager-supplied target-candidate rows, writes `trading_data.feature_03_strategy_variant_simulation`, and keeps ticker/company identity out of emitted feature rows.

CLI entrypoint:

```bash
trading-data-feature-03-strategy-variant-simulation --request-json request.json
```

Compatibility wrapper:

```bash
PYTHONPATH=src python3 scripts/generate_feature_03_strategy_variant_simulation.py --request-json request.json
```
