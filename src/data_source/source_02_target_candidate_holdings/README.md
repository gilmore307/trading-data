# source_02_target_candidate_holdings

Manager-facing ETF holdings source for downstream target-candidate preparation.

This source reads the reviewed ETF universe, keeps only `model_layer = layer_02_sector_context` rows, collects issuer holdings snapshots for those selected ETF symbols, filters holdings down to US-listed equity constituents, and writes the source-backed SQL table used after Layer 2 has selected/prioritized sector/industry baskets. Stable defaults live in pipeline code; there is no source-local `config.json`.

Boundary note: ETF holdings are not a core Layer 2 `SectorContextModel` behavior input. They belong to the anonymous target candidate builder / Layer 3 input-preparation boundary, where selected Layer 2 baskets are transmitted into stock candidates before target-state feature construction anonymizes model-facing vectors.

## Input parameters

Required task key fields:

- `source`: `source_02_target_candidate_holdings`
- `task_id`: stable task identifier
- `params.start`: inclusive holdings/as-of window start date or timestamp
- `params.end`: inclusive holdings/as-of window end date or timestamp
- `params.holding_feed_payloads`: object keyed by ETF symbol. Each value is an `06_feed_etf_holdings` feed payload parameter object such as `csv_path`, `csv_text`, `html_path`, `html`, `json_path`, or `json_text`.

Optional task key fields:

- `params.symbols`: comma string or list selecting a reviewed ETF subset from the universe
- `params.available_time`: explicit model-availability timestamp for all output rows. If omitted, the source derives a conservative session-open timestamp from `as_of_date`.
- `params.market_regime_etf_universe_path`: reviewed universe override. Normal runs use `/root/projects/trading-storage/main/shared/market_regime_etf_universe.csv`.
- `output_root`: local receipt/request-manifest root

The universe CSV supplies `symbol`, `issuer_name`, `model_layer`, `universe_type`, and `exposure_type`. Only `model_layer = layer_02_sector_context` rows require holdings analysis; `layer_01_market_regime` rows are Layer 1 regime/bar instruments and are intentionally skipped here. The holdings source supplies constituent rows.

## Filtering rule

Keep only ETF holdings that represent US-listed stock constituents accepted by the model universe. These rows are candidate-construction evidence, not Layer 2 sector behavior features.

Exclude:

- cash and money-market positions
- bonds, treasuries, and fixed income
- futures, swaps, options, warrants, and preferreds
- funds/ETFs inside ETF holdings
- non-US local listings and other non-equity assets unless explicitly reviewed

`cusip`, `sedol`, raw `asset_class`, and `source_url` are source evidence fields and are not part of the final model-input table.

## Output

Final saved output is SQL-only:

```text
source_02_target_candidate_holdings
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

`available_time` is the time the holdings row is allowed to become visible to model logic. If the feed supplies no explicit `available_time`, the conservative default is the next regular US session open after `as_of_date` (`09:30 America/New_York`, skipping weekends). Same-day availability requires explicit source evidence or reviewed task input; the pipeline must not assume a holdings file was visible before publication.

`run_id`, `task_id`, and task write/audit time belong in manifests and completion receipts, not in this business table.
