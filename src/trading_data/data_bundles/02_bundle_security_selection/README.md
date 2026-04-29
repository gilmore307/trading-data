# 02_bundle_security_selection

Manager-facing SecuritySelectionModel ETF holdings input bundle.

This bundle reads the reviewed ETF universe, collects issuer holdings snapshots for the selected ETF symbols, filters holdings down to US-listed equity constituents, and writes the source-backed SQL table consumed by SecuritySelectionModel. Stable defaults live in pipeline code; there is no bundle-local `config.json`.

## Input parameters

Required task key fields:

- `bundle`: `02_bundle_security_selection`
- `task_id`: stable task identifier
- `params.start`: inclusive holdings/as-of window start date or timestamp
- `params.end`: inclusive holdings/as-of window end date or timestamp
- `params.holding_source_payloads`: object keyed by ETF symbol. Each value is an `etf_holdings` source payload parameter object such as `csv_path`, `csv_text`, `html_path`, `html`, `json_path`, or `json_text`.

Optional task key fields:

- `params.symbols`: comma string or list selecting a reviewed ETF subset from the universe
- `params.available_time`: explicit model-availability timestamp for all output rows. If omitted, the bundle derives a conservative session-open timestamp from `as_of_date`.
- `params.market_etf_universe_path`: reviewed universe override. Normal runs use `/root/projects/trading-main/storage/shared/market_etf_universe.csv`.
- `output_root`: local receipt/request-manifest root

The universe CSV supplies `symbol`, `issuer_name`, `universe_type`, and `exposure_type`. The holdings source supplies constituent rows.

## Filtering rule

Keep only ETF holdings that represent US-listed stock constituents accepted by the model universe.

Exclude:

- cash and money-market positions
- bonds, treasuries, and fixed income
- futures, swaps, options, warrants, and preferreds
- funds/ETFs inside ETF holdings
- non-US local listings and other non-equity assets unless explicitly reviewed later

`cusip`, `sedol`, raw `asset_class`, and `source_url` are source evidence fields and are not part of the final model-input table.

## Output

Final saved output is SQL-only:

```text
trading_data.bundle_02_security_selection
```

Natural key:

```text
run_id + etf_symbol + as_of_date + holding_symbol
```

Columns:

- `run_id`
- `task_id`
- `etf_symbol`
- `issuer_name`
- `universe_type`
- `exposure_type`
- `as_of_date`
- `available_time`
- `holding_symbol`
- `holding_name`
- `weight`
- `shares`
- `market_value`
- `sector_type`

`available_time` is the time the holdings row is allowed to become visible to model logic. Task write/audit time belongs in the completion receipt, not in this business table.
