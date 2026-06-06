# m09_option_expression_data_acquisition

Manager-facing OptionExpressionModel option-chain snapshot input source.

This source accepts a manager-selected underlying, explicit snapshot time or bounded snapshot window, and entry/exit snapshot role. It derives Layer 9 rows from the shared `option_chain_state_source` and writes one SQL row per visible option contract per snapshot minute. The shared source/cache owns ThetaData option-chain provider calls. Stable defaults live in pipeline code; there is no source-local `config.json`.

## Input parameters

Required task key fields:

- `source`: `m09_option_expression_data_acquisition`
- `task_id`: stable task identifier
- `params.underlying`: underlying equity symbol
- `params.snapshot_time`: explicit point-in-time option-chain snapshot timestamp

Optional task key fields:

- `params.snapshot_type`: `entry` or `exit`; defaults to `entry` for compatibility
- `params.window_start` / `params.window_end`: optional bounded snapshot window; when present, existing `option_chain_state_source` rows are reused by `underlying + snapshot_time range` before any provider fetch
- `params.max_dte`: maximum days to expiration; defaults to `45`
- `params.strike_range`: ThetaData strike range bound; defaults to `5`
- `params.option_bucket_policy_ref`: Layer 9 bucket policy evidence; defaults to `LAYER_09_OPTION_BUCKET_STRIKE_POLICY`
- `params.reuse_option_chain_state_source`: defaults to enabled; set to `false` only for controlled provider-refresh tests
- `params.thetadata_transport`: defaults to `python_library`; set `terminal_rest` only for controlled fallback or fixture tests
- `params.thetadata_base_url`: local ThetaData Terminal/API base URL used only by `terminal_rest`
- `params.timeout_seconds`: request timeout
- `output_root`: local receipt/request-manifest root

## Output

Final saved outputs are SQL-only:

```text
option_chain_state_source
```

This shared source/cache table retains contract-level rows for Layer 3 target-level reduction and Layer 9 option-expression preparation.

```text
m09_option_expression_data_acquisition
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
- `bar_open`
- `bar_high`
- `bar_low`
- `bar_close`
- `bar_volume`
- `bar_trade_count`
- `bar_vwap`
- `trade_notional`
- `open_interest`
- `open_interest_change`

`option_symbol` uses the same normalized fallback format consumed by `m09_option_expression_data_acquisition_contract_path` selected-contract tracking when no provider-native symbol is supplied: `<UNDERLYING>_<expiration>_<C|P>_<strike>`.

The final Layer 9 table intentionally has no nested `contracts` JSONB column. Raw ThetaData responses and feed snapshot nesting are transient feed evidence. `snapshot_time` is the table's point-in-time contract row clock; quote/IV/Greeks provider row timestamps are intentionally omitted. `run_id`, `task_id`, and write/audit timestamps live in manifests and completion receipts, not in this business table. No saved source CSV mirror is written.
