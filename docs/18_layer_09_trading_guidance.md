# Layer 09 — Trading Guidance / Option Expression Data Boundary

<!-- ACTIVE_LAYER_REVISION -->
Status: active architecture revision. Layer 9 owns base trading guidance; `trading-data` owns option-expression features derived from the shared option-chain source plus selected-contract tracking used after expression selection.

Current feature/source names are `option_chain_state_source`, `m09_option_expression_feature_generation`, and `m09_option_expression_data_acquisition_contract_path`. `option_chain_state_source` is acquired before Layer 3 only when the selected target is option-applicable, then shared by Layer 3 and Layer 9. Targets marked as `crypto_spot` or confirmed no-listed-options have no Layer 9 option-expression feature path.
<!-- /ACTIVE_LAYER_REVISION -->


`trading-data` owns option-expression source inputs for Layer 9. Model-side contract ranking, expression choice, labels, evaluation, and promotion belong to `trading-model`.

## Owned artifacts

```text
trading_data.option_chain_state_source
trading_data.m09_option_expression_feature_generation
trading_data.m09_option_expression_data_acquisition_contract_path
```

- `option_chain_state_source` is the shared contract-level option-chain source/cache.
- `m09_option_expression_feature_generation` derives option-expression candidate rows from `option_chain_state_source` for `TradingGuidanceModel / OptionExpressionModel`.
- `m09_option_expression_data_acquisition_contract_path` is selected-contract option market-data tracking for replay/evaluation.

## Boundary

Layer 9 data covers visible option-chain evidence, deterministic option-candidate features, and selected-contract market paths.

`option_chain_state_source` writes one row per visible contract at an explicit snapshot time. It captures quote, spread, IV, first-order Greeks, trade-summary fields, and contract identity where provider data is available. Layer 3 may reduce these rows into target-level option state but must not expose contract identity or executable option terms.

`m09_option_expression_feature_generation` derives source-only per-contract candidate features directly from accepted shared snapshot rows: moneyness, spread/liquidity, IV, Greeks availability, and quality diagnostics. It prepares model inputs without ranking contracts or choosing an expression.

`m09_option_expression_data_acquisition_contract_path` writes selected option contract bars from entry time through exit time plus one hour. It emits market data only.

## Stage flow

```text
ThetaData option feeds
  -> option_chain_state_source shared option-chain source/cache
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
