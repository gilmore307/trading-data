# 05_source_option_expression

Manager-facing OptionExpressionModel option-chain snapshot input source.

This source accepts a manager-selected underlying, explicit snapshot time, and entry/exit snapshot role, calls the ThetaData option selection snapshot feed interface, and writes one SQL row per visible option contract. Stable defaults live in pipeline code; there is no source-local `config.json`.

## Input parameters

Required task key fields:

- `source`: `05_source_option_expression`
- `task_id`: stable task identifier
- `params.underlying`: underlying equity symbol
- `params.snapshot_time`: explicit point-in-time option-chain snapshot timestamp

Optional task key fields:

- `params.snapshot_type`: `entry` or `exit`; defaults to `entry` for compatibility
- `params.thetadata_base_url`: local ThetaData terminal/API base URL
- `params.timeout_seconds`: request timeout
- `output_root`: local receipt/request-manifest root

## Output

Final saved output is SQL-only:

```text
source_05_option_expression
```

Natural key:

```text
underlying + snapshot_time + snapshot_type + option_symbol
```

Columns:

- `underlying`
- `snapshot_time`
- `snapshot_type`
- `option_symbol`
- `expiration`
- `option_right_type`
- `strike`
- `bid`
- `ask`
- `mid`
- `spread`
- `spread_pct`
- `bid_size`
- `ask_size`
- `bid_exchange`
- `ask_exchange`
- `bid_condition`
- `ask_condition`
- `implied_vol`
- `iv_error`
- `delta`
- `theta`
- `vega`
- `rho`
- `epsilon`
- `lambda`
- `underlying_price`
- `underlying_timestamp`
- `days_to_expiration`

`option_symbol` uses the same normalized fallback format consumed by Layer 06 when no provider-native symbol is supplied: `<UNDERLYING>_<expiration>_<C|P>_<strike>`.

The final table intentionally has no nested `contracts` JSONB column. Raw ThetaData responses and feed snapshot nesting are transient feed evidence. `snapshot_time` is the table's point-in-time clock; quote/IV/Greeks provider row timestamps are intentionally omitted. `run_id`, `task_id`, and write/audit timestamps live in manifests and completion receipts, not in this business table. No saved source CSV mirror is written.
