# source_06_position_execution

Manager-facing PositionExecutionModel data source.

Layer 06 answers how selected option contracts could be executed. The source accepts multiple contracts selected by Layer 05 and writes option contract time-series rows from each contract's entry time through one hour after its exit time.

Stable defaults live in pipeline code; there is no source-local `config.json`.

## Input parameters

Required task key fields:

- `source`: `source_06_position_execution`
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
- `thetadata_base_url`, `timeout_seconds`, `registry_csv`: passed through when fetching from ThetaData primary tracking.

## Output

Final saved output is SQL-only:

```text
source_06_position_execution
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
