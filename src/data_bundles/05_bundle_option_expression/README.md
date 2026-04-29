# 05_bundle_option_expression

Manager-facing OptionExpressionModel option-chain snapshot input bundle.

This bundle accepts a manager-selected underlying and explicit snapshot time, calls the ThetaData option selection snapshot source interface, and writes the visible option-chain snapshot to SQL. Stable defaults live in pipeline code; there is no bundle-local `config.json`.

## Input parameters

Required task key fields:

- `bundle`: `05_bundle_option_expression`
- `task_id`: stable task identifier
- `params.underlying`: underlying equity symbol
- `params.snapshot_time`: explicit point-in-time option-chain snapshot timestamp

Optional task key fields:

- `params.thetadata_base_url`: local ThetaData terminal/API base URL
- `params.timeout_seconds`: request timeout
- `output_root`: local receipt/request-manifest root

## Output

Final saved output is SQL-only:

```text
bundle_05_option_expression
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
