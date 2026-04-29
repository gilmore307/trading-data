# 05_bundle_option_expression

Manager-facing OptionExpressionModel option-chain snapshot input bundle.

This bundle accepts a manager-selected underlying, explicit snapshot time, and entry/exit snapshot role, calls the ThetaData option selection snapshot source interface, and writes one SQL row per visible option contract. Stable defaults live in pipeline code; there is no bundle-local `config.json`.

## Input parameters

Required task key fields:

- `bundle`: `05_bundle_option_expression`
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
bundle_05_option_expression
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
- `quote_timestamp`
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
- `iv_timestamp`
- `implied_vol`
- `iv_error`
- `greeks_timestamp`
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

The final table intentionally has no nested `contracts` JSONB column. Raw ThetaData responses and source snapshot nesting are transient source evidence. `run_id`, `task_id`, and write/audit timestamps live in manifests and completion receipts, not in this business table. No saved bundle CSV is written.
