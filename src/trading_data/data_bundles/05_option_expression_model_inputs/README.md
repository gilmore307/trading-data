# 05_option_expression_model_inputs

Manager-facing OptionExpressionModel option-chain snapshot input bundle.

This bundle accepts a manager-selected underlying and explicit snapshot time, calls the ThetaData option selection snapshot source interface, and writes the full visible option chain to SQL as one row with nested contracts payload.

## Input parameters

Required task key fields:

- `bundle`: `05_option_expression_model_inputs`
- `task_id`: stable task identifier
- `params.underlying`: underlying equity symbol
- `params.snapshot_time`: explicit point-in-time option-chain snapshot timestamp

Optional task key fields:

- `params.thetadata_base_url`: local ThetaData terminal/API base URL
- `params.timeout_seconds`: request timeout
- `params.config_path`: reviewed config override
- `output_root`: local receipt/request-manifest root

## Output

Final saved output is SQL-only:

```text
model_inputs.option_expression_option_chain_snapshot
```

Natural key:

```text
run_id + underlying + snapshot_time
```

Columns:

- `run_id`
- `task_id`
- `underlying`
- `snapshot_time`
- `contract_count`
- `contracts`

`contracts` is the complete normalized nested option-chain payload for visible contracts at the snapshot time. Raw ThetaData responses are transient and are not persisted by default. No saved bundle CSV is written.
