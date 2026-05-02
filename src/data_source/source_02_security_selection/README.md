# source_02_security_selection

Manager-facing ETF holdings source for downstream target-candidate preparation.

This source reads the reviewed ETF universe, keeps only `universe_type = sector_observation_etf`, collects issuer holdings snapshots for those selected ETF symbols, filters holdings down to US-listed equity constituents, and writes the source-backed SQL table used after Layer 2 has selected/prioritized sector/industry baskets. Stable defaults live in pipeline code; there is no source-local `config.json`.

Boundary note: the physical source/table name remains `source_02_security_selection` for now, but ETF holdings are no longer a core Layer 2 `SecuritySelectionModel` behavior input. They belong to the anonymous target candidate builder / Layer 3 input-preparation boundary, where selected Layer 2 baskets are transmitted into stock candidates before strategy fitting anonymizes target vectors.

## Input parameters

Required task key fields:

- `source`: `source_02_security_selection`
- `task_id`: stable task identifier
- `params.start`: inclusive holdings/as-of window start date or timestamp
- `params.end`: inclusive holdings/as-of window end date or timestamp
- `params.holding_feed_payloads`: object keyed by ETF symbol. Each value is an `06_feed_etf_holdings` feed payload parameter object such as `csv_path`, `csv_text`, `html_path`, `html`, `json_path`, or `json_text`.

Optional task key fields:

- `params.symbols`: comma string or list selecting a reviewed ETF subset from the universe
- `params.available_time`: explicit model-availability timestamp for all output rows. If omitted, the source derives a conservative session-open timestamp from `as_of_date`.
- `params.market_regime_etf_universe_path`: reviewed universe override. Normal runs use `/root/projects/trading-storage/main/shared/market_regime_etf_universe.csv`.
- `output_root`: local receipt/request-manifest root

The universe CSV supplies `symbol`, `issuer_name`, `universe_type`, and `exposure_type`. Only `sector_observation_etf` rows require holdings analysis; `market_state_etf` rows are Layer 1 regime/bar instruments and are intentionally skipped here. The holdings source supplies constituent rows.

## Filtering rule

Keep only ETF holdings that represent US-listed stock constituents accepted by the model universe. These rows are candidate-construction evidence, not Layer 2 sector behavior features.

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
source_02_security_selection
```

Natural key:

```text
etf_symbol + as_of_date + holding_symbol
```

Columns:

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

`available_time` is the time the holdings row is allowed to become visible to model logic. `run_id`, `task_id`, and task write/audit time belong in manifests and completion receipts, not in this business table.
