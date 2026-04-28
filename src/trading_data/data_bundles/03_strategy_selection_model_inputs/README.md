# 03_strategy_selection_model_inputs

Manager-facing StrategySelectionModel bar/liquidity input bundle.

This bundle accepts manager-selected symbols over a requested time range, fetches Alpaca bars plus transient trade/quote liquidity inputs, aggregates them to the configured interval, and writes one SQL table for StrategySelectionModel inputs.

## Input parameters

Required task key fields:

- `bundle`: `03_strategy_selection_model_inputs`
- `task_id`: stable task identifier
- `params.start`: inclusive request start timestamp/date
- `params.end`: exclusive request end timestamp/date
- `params.symbols`: comma string or JSON list of manager-selected symbols

Optional task key fields:

- `params.timeframe`: bar/liquidity interval. Default comes from config and is `1Min`.
- `params.config_path`: reviewed config override
- `params.limit`, `params.max_pages`, `params.adjustment`, `params.feed`, `params.timeout_seconds`: request/runtime overrides
- `output_root`: local receipt/request-manifest root

## Config

`config.json` owns only source/default output settings for this bundle:

- Alpaca secret alias
- default timeframe: `1Min`
- request defaults
- PostgreSQL storage target
- SQL output table contract

Liquidity thresholds and feature windows are intentionally not in this bundle. Strategy features such as returns, volatility, trend strength, gap logic, and model scoring are downstream feature/model responsibilities.

## Output

Final saved output is SQL-only:

```text
model_inputs.strategy_selection_symbol_bar_liquidity
```

Natural key:

```text
run_id + symbol + timeframe + timestamp
```

Columns:

- `run_id`
- `task_id`
- `symbol`
- `timeframe`
- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `vwap`
- `trade_count`
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

No saved bundle CSV is written. Task write/audit timestamps belong in the completion receipt, not this business table.
