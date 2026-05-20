# feature_09_option_expression

Deterministic option-expression feature builder for the Layer 9 trading-guidance option-expression subset.

## Boundary

Input is accepted `source_05_option_expression` option-chain snapshot rows. Output
is a compact per-contract feature surface for the `TradingGuidanceModel /
OptionExpressionModel` input boundary. The package name remains legacy until a
dedicated physical rename migration is accepted.

Selected-contract market-path rows from `source_06_position_execution` remain
replay/evaluation evidence; they are not order instructions and are not required
for the per-snapshot candidate feature table.

## Output table

```text
trading_data.feature_09_option_expression
```

Rows are keyed by `underlying + snapshot_time + snapshot_type + option_symbol`
and store deterministic option candidate features in JSONB.
