# m05_option_expression_data_acquisition_contract_path

Manager-facing selected-option-contract market-path tracking source.

This source supports M05 OptionExpressionModel replay/evaluation by collecting the market path of contracts selected by an upstream offline option-expression plan. It is not broker execution, not M04 risk `DynamicRiskPolicyModel`, not a model-output layer, and does not emit execution instructions. The source accepts multiple selected contracts and writes option contract time-series rows from each contract's entry time through one hour after its exit time.

Stable defaults live in pipeline code; there is no source-local `config.json`.

## Input parameters

Required task key fields:

- `source`: `m05_option_expression_data_acquisition_contract_path`
- `task_id`: stable task identifier
- `params.selected_contracts`: non-empty list of contracts selected by OptionExpressionModel

Each selected contract requires:

- `underlying`
- `expiration`
- `option_right_type` or provider-style `right`
- `strike`
- `entry_time`
- `exit_time`

Optional per-contract fields:

- `option_symbol`: preferred stable contract symbol. If omitted, the source derives one from underlying/expiration/right/strike.
- `timeframe`: default `1Min`.
- `option_rows` / `timeseries_rows`: reviewed inline rows, mainly for tests or upstream replay.
- `thetadata_transport`, `thetadata_credentials_file`, `thetadata_base_url`, `timeout_seconds`, `retry_attempts`, `retry_backoff_seconds`, `registry_csv`: passed through when fetching from ThetaData primary tracking.

Default provider acquisition uses the ThetaData Python library exact OHLC route through `10_feed_thetadata_option_primary_tracking`. `terminal_rest` is an explicit fallback/testing transport.

## Output

Final saved output is SQL-only:

```text
trading_data.model_05_option_expression_data_acquisition_contract_path
```

Natural key:

```text
option_symbol + timeframe + timestamp
```

Columns:

- `underlying`
- `option_symbol`
- `expiration`
- `option_right_type`
- `strike`
- `timeframe`
- `timestamp`
- `bar_open`
- `bar_high`
- `bar_low`
- `bar_close`
- `bar_volume`
- `bar_trade_count`
- `bar_vwap`

The table contains market data only. It does not include position sizing, order decisions, risk scores, PnL labels, or execution recommendations. Task/run lineage stays in the completion receipt.
