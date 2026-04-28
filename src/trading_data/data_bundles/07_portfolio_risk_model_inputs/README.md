# 07_portfolio_risk_model_inputs

PortfolioRiskModel inputs manager-facing data bundle.

This bundle accepts a manager task key, loads bundle-local `config.json`, and writes a point-in-time model-input manifest CSV. It does not fetch raw provider data directly; source acquisition remains in `trading_data.data_sources`.

## Required task params

- `as_of` — America/New_York timestamp for the point-in-time input manifest.
- `input_paths` — object mapping configured input roles to one path or a list of paths.

## Configured inputs

- `option_expression_candidates` -> `option_expression_model_inputs` (required)
- `positions` -> `portfolio_position_snapshot` (optional)
- `cash_buying_power` -> `account_snapshot` (optional)
- `open_orders` -> `open_order_snapshot` (optional)
- `risk_limits` -> `risk_limit_config` (optional)

## Output

`saved/07_portfolio_risk_model_inputs.csv`
