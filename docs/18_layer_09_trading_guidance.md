# Layer 09 — Trading Guidance / Option Expression Data Boundary

<!-- ACTIVE_LAYER_REVISION -->
Status: active architecture revision. Layer 9 owns base trading guidance; `trading-data` owns option-expression source inputs used by the option-expression subset of Layer 9.

Current feature/source names are `m09_option_expression_data_acquisition`, `m09_option_expression_feature_generation`, and `m09_option_expression_data_acquisition_contract_path`. These persistent names follow the current `mNN_<domain>_<stage>` physical table standard; the conceptual model boundary is Layer 9.
<!-- /ACTIVE_LAYER_REVISION -->


`trading-data` owns option-expression source inputs for Layer 9. Model-side contract ranking, expression choice, labels, evaluation, and promotion belong to `trading-model`.

## Owned artifacts

```text
trading_data.m09_option_expression_data_acquisition
trading_data.m09_option_expression_feature_generation
trading_data.m09_option_expression_data_acquisition_contract_path
```

- `m09_option_expression_data_acquisition` is the option-chain snapshot input for `TradingGuidanceModel / OptionExpressionModel`.
- `m09_option_expression_data_acquisition_contract_path` is selected-contract option market-data tracking for replay/evaluation.

## Boundary

Layer 9 data covers visible option-chain evidence, deterministic option-candidate features, and selected-contract market paths.

`m09_option_expression_data_acquisition` writes one row per visible contract at an explicit entry/exit snapshot time. It captures quote, spread, IV, first-order Greeks, and contract identity where provider data is available.

`m09_option_expression_feature_generation` derives source-only per-contract candidate features from accepted snapshot rows: moneyness, spread/liquidity, IV, Greeks availability, and quality diagnostics. It prepares model inputs without ranking contracts or choosing an expression.

`m09_option_expression_data_acquisition_contract_path` writes selected option contract bars from entry time through exit time plus one hour. It emits market data only.

## Stage flow

```text
ThetaData option feeds
  -> m09_option_expression_data_acquisition option-chain snapshot
  -> m09_option_expression_feature_generation
  -> trading-model TradingGuidanceModel / OptionExpressionModel
  -> selected contract handoff
  -> m09_option_expression_data_acquisition_contract_path selected-contract tracking
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
