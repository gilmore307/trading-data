# 03_bundle_strategy_selection

Manager-facing StrategySelectionModel bar/liquidity input bundle.

This bundle accepts manager-selected symbols over a requested time range, fetches Alpaca bars plus transient trade/quote liquidity inputs, aggregates them to the requested interval, and writes one SQL table for StrategySelectionModel inputs. Stable defaults live in pipeline code; there is no bundle-local `config.json`.

## Input parameters

Required task key fields:

- `bundle`: `03_bundle_strategy_selection`
- `task_id`: stable task identifier
- `params.start`: inclusive request start timestamp/date
- `params.end`: exclusive request end timestamp/date
- `params.symbols`: comma string or JSON list of manager-selected symbols

Optional task key fields:

- `params.timeframe`: bar/liquidity interval. Default is `1Min`.
- `params.limit`, `params.max_pages`, `params.adjustment`, `params.feed`, `params.timeout_seconds`, `params.secret_alias`: request/runtime overrides
- `output_root`: local receipt/request-manifest root

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
