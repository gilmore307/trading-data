# 05_option_expression_model_inputs

OptionExpressionModel inputs manager-facing data bundle.

This bundle accepts a manager task key, loads bundle-local `config.json`, and writes a point-in-time model-input manifest CSV. It does not fetch raw provider data directly; source acquisition remains in `trading_data.data_sources`.

## Required task params

- `as_of` — America/New_York timestamp for the point-in-time input manifest.
- `input_paths` — object mapping configured input roles to one path or a list of paths.

## Configured inputs

- `option_chain_snapshot` -> `option_chain_snapshot` (required)
- `option_bars` -> `option_bar` (optional)
- `trade_quality_candidates` -> `trade_quality_model_inputs` (required)
- `option_activity_events` -> `option_activity_event` (optional)

## Output

`saved/05_option_expression_model_inputs.csv`
