# Layer 09 — Trading Guidance / Option Expression Data Boundary

<!-- ACTIVE_LAYER_REVISION -->
Status: active architecture revision. Layer 9 owns base trading guidance; `trading-data` owns option-expression source inputs used by the option-expression subset of Layer 9.

Current feature/source names are `source_05_option_expression`, `feature_09_option_expression`, and `source_06_position_execution`. The source numbers are accepted data-source identifiers; the conceptual model boundary is Layer 9.
<!-- /ACTIVE_LAYER_REVISION -->


`trading-data` owns option-expression source inputs for Layer 9. Model-side contract ranking, expression choice, labels, evaluation, and promotion belong to `trading-model`.

## Owned artifacts

```text
trading_data.source_05_option_expression
trading_data.feature_09_option_expression
trading_data.source_06_position_execution
```

The source numbers remain historical/accepted source identifiers:

- `source_05_option_expression` is the option-chain snapshot input for `TradingGuidanceModel / OptionExpressionModel`.
- `source_06_position_execution` is selected-contract option market-data tracking for replay/evaluation.

Neither source is model Layer 5 or Layer 6.

## Boundary

Layer 9 data covers visible option-chain evidence, deterministic option-candidate features, and selected-contract market paths.

`source_05_option_expression` writes one row per visible contract at an explicit entry/exit snapshot time. It captures quote, spread, IV, first-order Greeks, and contract identity where provider data is available.

`feature_09_option_expression` derives source-only per-contract candidate features from accepted snapshot rows: moneyness, spread/liquidity, IV, Greeks availability, and quality diagnostics. It prepares model inputs without ranking contracts or choosing an expression.

`source_06_position_execution` writes selected option contract bars from entry time through exit time plus one hour. It emits market data only.

## Stage flow

```text
ThetaData option feeds
  -> source_05_option_expression option-chain snapshot
  -> feature_09_option_expression
  -> trading-model TradingGuidanceModel / OptionExpressionModel
  -> selected contract handoff
  -> source_06_position_execution selected-contract tracking
  -> replay/evaluation outside trading-data
```

## Non-ownership

`trading-data` does not own:

- contract ranking;
- final expression choice;
- theoretically best-return label design;
- risk-controllable expression scoring;
- order instructions;
- execution decisions;
- PnL labels;
- production promotion decisions.

## Acceptance notes

Layer 9 data changes are acceptable when they:

- preserve explicit point-in-time snapshot times;
- keep ThetaData raw provider rows transient by default;
- write reviewed SQL source outputs or compact reviewed artifacts;
- keep selected-contract tracking as market data only;
- route reusable option fields, statuses, and artifact names through `trading-manager` before cross-repository dependence.