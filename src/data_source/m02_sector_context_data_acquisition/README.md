# m02_sector_context_data_acquisition

Retired manager-facing ETF holdings evidence source.

This source reads the reviewed ETF universe, keeps only `model_layer = model_01_sector_context` rows, collects issuer holdings snapshots for those selected ETF symbols, filters holdings down to US-listed equity constituents, and writes the source-backed SQL table when explicitly run. Stable defaults live in pipeline code; there is no source-local `config.json`.

Boundary note: ETF holdings are not a core M02 `SectorContextModel` behavior input. They do not define the realtime total-symbol pool, ordinary target candidates, or historical replay candidates. The current M02 feature stage does not materialize this source. If ETF holdings evidence is revived for target-specific exposure analysis, it needs a separate reviewed proxy/theme or exposure-evidence contract.

## Input parameters

Required task key fields:

- `source`: `m02_sector_context_data_acquisition`
- `task_id`: stable task identifier
- `params.start`: inclusive holdings/as-of window start date or timestamp
- `params.end`: inclusive holdings/as-of window end date or timestamp

Optional task key fields:

- `params.holding_feed_payloads`: object keyed by ETF symbol. Each value is an `06_feed_etf_holdings` feed payload parameter object such as `csv_path`, `csv_text`, `html_path`, `html`, `json_path`, `json_text`, or an explicit `source_url`. If no payload is supplied for a selected ETF, the holdings feed tries the accepted fixed official issuer URL adapter.
- `params.symbols`: comma string or list selecting a reviewed ETF subset from the universe
- `params.continue_on_error`: when true, one ETF issuer failure is recorded in the run manifest and does not prevent other issuer rows from being written.
- `params.available_time`: explicit model-availability timestamp for all output rows. If omitted, the source derives a conservative session-open timestamp from `as_of_date`.
- `params.market_regime_etf_universe_path`: reviewed universe override. Normal runs use `TRADING_STORAGE_REPO_ROOT/main/shared/model_01_background_context_etf_universe.csv`, defaulting to the sibling `trading-storage` repository.
- `output_root`: local receipt/request-manifest root

The universe CSV supplies `symbol`, `issuer_name`, `model_layer`, `universe_type`, and `exposure_type`. Only `model_layer = model_01_sector_context` rows require holdings analysis; `model_01_market_context` rows are M01 regime/bar instruments and are intentionally skipped here. The holdings source supplies constituent rows.

## Filtering rule

Keep only ETF holdings that represent US-listed stock constituents accepted by the model universe. These rows are candidate-construction evidence, not M02 sector behavior features.

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
m02_sector_context_data_acquisition
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
