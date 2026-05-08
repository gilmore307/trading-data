# feature_08_option_expression

Deterministic Layer 8 option-expression feature builder.

## Boundary

Input is accepted `source_05_option_expression` option-chain snapshot rows. Output
is a compact per-contract feature surface for `OptionExpressionModel` input
preparation.

Selected-contract market-path rows from `source_06_position_execution` remain
replay/evaluation evidence; they are not order instructions and are not required
for the per-snapshot candidate feature table.

## Output table

```text
trading_data.feature_08_option_expression
```

Rows are keyed by `underlying + snapshot_time + snapshot_type + option_symbol`
and store deterministic option candidate features in JSONB.
