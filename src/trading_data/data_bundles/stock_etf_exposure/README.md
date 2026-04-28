# stock_etf_exposure

Derived model-input bundle for `SecuritySelectionModel`.

## Boundary

- Input: saved `etf_holding_snapshot.csv` files from the official issuer holdings bundle.
- Output: final saved `stock_etf_exposure.csv`.
- No live fetch. No raw provider payload. This is a point-in-time feature bridge from ETF/sector/theme strength to tradable stock symbols.

## Required params

- `holdings_csv_paths` — one path or list of saved ETF holdings CSV paths.
- `available_time_et` — earliest America/New_York timestamp when the exposure row is usable.

## Optional params

- `as_of_date` — fallback holdings date when source rows omit it.
- `etf_scores` — object keyed by ETF ticker; values may include:
  - `sector_score`
  - `theme_score`
  - `style_tags`

## Output

`saved/stock_etf_exposure.csv` with the registered model-input columns.
