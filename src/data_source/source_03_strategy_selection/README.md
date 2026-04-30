# source_03_strategy_selection

Manager-facing StrategySelectionModel bar/liquidity input source.

This source accepts manager-selected symbols over a requested time range, fetches Alpaca bars plus transient trade/quote liquidity inputs, aggregates them to the requested interval, and writes one SQL table for StrategySelectionModel inputs. Stable defaults live in pipeline code; there is no source-local `config.json`.

## Input parameters

Required task key fields:

- `source`: `source_03_strategy_selection`
- `task_id`: stable task identifier
- `params.start`: inclusive request start timestamp/date
- `params.end`: exclusive request end timestamp/date
- `params.symbols`: comma string or JSON list of manager-selected symbols

Optional task key fields:

- `params.timeframe`: bar/liquidity interval. Default is `1Min`.
- `params.limit`, `params.max_pages`, `params.adjustment`, `params.feed`, `params.timeout_seconds`, `params.secret_alias`: request/runtime overrides
- `output_root`: local receipt/request-manifest root

Liquidity thresholds and feature windows are intentionally not in this source. Strategy features such as returns, volatility, trend strength, gap logic, and model scoring are downstream feature/model responsibilities.

## Output

Final saved output is SQL-only:

```text
source_03_strategy_selection
```

Natural key:

```text
symbol + timeframe + timestamp
```

Columns:

- `symbol`
- `timeframe`
- `timestamp`
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

No saved source CSV mirror is written. `run_id`, `task_id`, and task write/audit timestamps belong in manifests and completion receipts, not this business table.
