# 02_security_selection_model_inputs

SecuritySelectionModel inputs manager-facing data bundle.

This bundle accepts a manager task key, loads bundle-local `config.json`, and writes a point-in-time model-input manifest CSV. It does not fetch raw provider data directly; source acquisition remains in `trading_data.data_sources`.

## Required task params

- `as_of_et` — America/New_York timestamp for the point-in-time input manifest.
- `input_paths` — object mapping configured input roles to one path or a list of paths.

## Configured inputs

- `stock_etf_exposure` -> `stock_etf_exposure` (required)
- `equity_bars` -> `equity_bar` (required)
- `equity_liquidity` -> `equity_liquidity_bar` (optional)
- `event_exclusions` -> `trading_event` (optional)

## Output

`saved/02_security_selection_model_inputs.csv`
