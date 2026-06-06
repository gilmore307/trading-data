# m09_option_expression_feature_generation

Deterministic option-expression feature builder for the Layer 9 trading-guidance option-expression subset.

## Boundary

Input is accepted shared `option_chain_state_source` option-chain snapshot rows.
Output is a compact per-contract feature surface for the `TradingGuidanceModel /
OptionExpressionModel` input boundary. The package name is the accepted physical
feature package for this boundary.

Selected-contract market-path rows from `m09_option_expression_data_acquisition_contract_path` remain
replay/evaluation evidence; they are not order instructions and are not required
for the per-snapshot candidate feature table.

## Output table

```text
trading_data.m09_option_expression_feature_generation
```

Rows are keyed by `underlying + snapshot_time + snapshot_type + option_symbol`
and store deterministic option candidate features in JSONB.
