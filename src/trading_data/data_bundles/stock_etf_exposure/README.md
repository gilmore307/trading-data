# stock_etf_exposure

Derived model-input bundle for `SecuritySelectionModel`.

## Boundary

- Input: saved `etf_holding_snapshot.csv` files from the official issuer holdings bundle.
- Output: final saved `stock_etf_exposure.csv`.
- No live fetch. No raw provider payload. This is a point-in-time feature bridge from ETF/sector/theme strength to tradable stock symbols.

## Required params

- `holdings_csv_paths` — one path or list of saved ETF holdings CSV paths.
- `available_time_et` — earliest America/New_York timestamp when the exposure row is usable.

## Bundle config

`config.json` lives in this bundle folder and owns reusable defaults such as ETF universe, issuer labels, desired grains, and default ETF scores. Task keys may override run-specific values.

## Optional params

- `as_of_date` — fallback holdings date when source rows omit it.
- `config_path` — reviewed one-off config override path; normal runs use bundle-local `config.json`.
- `etf_scores` — object keyed by ETF ticker; values may include:
  - `sector_score`
  - `theme_score`
  - `style_tags`

## Output

`saved/stock_etf_exposure.csv` with the registered model-input columns.
