# 04_trade_quality_model_inputs

TradeQualityModel inputs manager-facing data bundle.

This bundle accepts a manager task key, loads bundle-local `config.json`, and writes a point-in-time model-input manifest CSV. It does not fetch raw provider data directly; source acquisition remains in `trading_data.data_sources`.

## Required task params

- `as_of_et` — America/New_York timestamp for the point-in-time input manifest.
- `input_paths` — object mapping configured input roles to one path or a list of paths.

## Configured inputs

- `strategy_candidates` -> `strategy_selection_model_inputs` (required)
- `market_context` -> `market_regime_model_inputs` (required)
- `security_context` -> `security_selection_model_inputs` (required)
- `outcome_labels` -> `trade_quality_label` (optional)

## Output

`saved/04_trade_quality_model_inputs.csv`
