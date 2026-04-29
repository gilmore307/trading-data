# 06_bundle_position_execution

Manager-facing PositionExecutionModel data bundle.

Layer 06 answers how selected option contracts could be executed. The bundle accepts multiple contracts selected by Layer 05 and writes option contract time-series rows from each contract's entry time through one hour after its exit time.

Stable defaults live in pipeline code; there is no bundle-local `config.json`.

## Input parameters

Required task key fields:

- `bundle`: `06_bundle_position_execution`
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

- `option_symbol`: preferred stable contract symbol. If omitted, the bundle derives one from underlying/expiration/right/strike.
- `timeframe`: default `1Min`.
- `option_rows` / `timeseries_rows`: reviewed inline rows, mainly for tests or upstream replay.
- `thetadata_base_url`, `timeout_seconds`, `registry_csv`: passed through when fetching from ThetaData primary tracking.

## Output

Final saved output is SQL-only:

```text
model_inputs.trading_data_06_bundle_position_execution
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
- `open`
- `high`
- `low`
- `close`
- `volume`
- `trade_count`
- `vwap`

The table contains market data only. It does not include position sizing, order decisions, risk scores, PnL labels, or execution recommendations. Task/run lineage stays in the completion receipt.
