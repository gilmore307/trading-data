# 03_strategy_selection_model_inputs

StrategySelectionModel inputs manager-facing data bundle.

This bundle accepts a manager task key, loads bundle-local `config.json`, and writes a point-in-time model-input manifest CSV. It does not fetch raw provider data directly; source acquisition remains in `trading_data.data_sources`.

## Required task params

- `as_of` — America/New_York timestamp for the point-in-time input manifest.
- `input_paths` — object mapping configured input roles to one path or a list of paths.

## Configured inputs

- `selected_universe` -> `stock_etf_exposure` (required)
- `equity_bars` -> `equity_bar` (required)
- `equity_liquidity` -> `equity_liquidity_bar` (optional)
- `crypto_bars` -> `crypto_bar` (optional)
- `crypto_liquidity` -> `crypto_liquidity_bar` (optional)

## Output

`saved/03_strategy_selection_model_inputs.csv`
