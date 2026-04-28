# market_regime_model_inputs

MarketRegimeModel inputs manager-facing data bundle.

This bundle accepts a manager task key, loads bundle-local `config.json`, and writes a point-in-time model-input manifest CSV. It does not fetch raw provider data directly; source acquisition remains in `trading_data.data_sources`.

## Required task params

- `as_of_et` — America/New_York timestamp for the point-in-time input manifest.
- `input_paths` — object mapping configured input roles to one path or a list of paths.

## Configured inputs

- `broad_market_bars` -> `equity_bar` (required)
- `sector_etf_bars` -> `equity_bar` (required)
- `cross_asset_etf_bars` -> `equity_bar` (optional)

## Output

`saved/market_regime_model_inputs.csv`
