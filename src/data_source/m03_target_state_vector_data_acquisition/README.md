# m03_target_state_vector_data_acquisition

Deterministic Layer 3 target-local observed-input source for `TargetStateVectorModel`.

This package normalizes caller-supplied, point-in-time target-local bars plus optional aggregate liquidity/quote evidence into SQL rows for:

```text
trading_data.model_03_target_state_vector_data_acquisition
```

It performs no provider calls. Raw bulky provider responses, tick trades, and tick quotes are not persisted by this source.

## Input parameters

Required task key fields:

- `source`: `m03_target_state_vector_data_acquisition`
- `task_id`: stable task identifier
- either `params.bar_sql_sources`, inline bar rows, or local fixture bar paths
- or `params.liquidity_rows` / `params.liquidity_bars` / local liquidity path

Recommended parameters:

- `params.target_candidates` or `params.candidate_rows`: rows with `target_candidate_id` plus `symbol`, `routing_symbol_ref`, or `audit_symbol_ref`
- `params.start`, `params.end`: optional inclusive point-in-time bounds
- `params.timeframe`: default timeframe for rows missing their own `timeframe`; default `1Min`
- `output_root`: local manifest/receipt root

Production manager runs use `params.bar_sql_sources` to read SQL-retained Alpaca bars from `trading_data.model_01_market_regime_data_acquisition`. The source does not require `equity_bar.jsonl` or `equity_bar.csv` payload files.

Local path variants remain accepted for fixtures and controlled debug tasks: `bars_path`, `bars_csv_path`, `bars_json_path`, `liquidity_rows_path`, `liquidity_csv_path`, `liquidity_json_path`, `target_candidates_path`, and `candidate_rows_path`.

## Output

Final saved output is SQL-only:

```text
m03_target_state_vector_data_acquisition
```

Natural key:

```text
target_candidate_id + timeframe + timestamp
```

Columns:

- `target_candidate_id`
- `symbol`
- `timeframe`
- `timestamp`
- `available_time`
- `bar_open`
- `bar_high`
- `bar_low`
- `bar_close`
- `bar_volume`
- `bar_vwap`
- `bar_trade_count`
- `dollar_volume`
- `quote_count`
- `avg_bid`
- `avg_ask`
- `avg_bid_size`
- `avg_ask_size`
- `avg_spread`
- `spread_bps`
- `last_bid`
- `last_ask`

`symbol` is retained only as source/audit/routing metadata. Model-facing feature blocks must use `target_candidate_id` and must not include ticker/company identity.
