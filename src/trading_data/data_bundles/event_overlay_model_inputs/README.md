# event_overlay_model_inputs

EventOverlayModel inputs manager-facing data bundle.

This bundle accepts a manager task key, loads bundle-local `config.json`, and writes a point-in-time model-input manifest CSV. It does not fetch raw provider data directly; source acquisition remains in `trading_data.data_sources`.

## Required task params

- `as_of_et` — America/New_York timestamp for the point-in-time input manifest.
- `input_paths` — object mapping configured input roles to one path or a list of paths.

## Configured inputs

- `gdelt_articles` -> `gdelt_article` (optional)
- `sec_company_financials` -> `sec_company_fact` (optional)
- `trading_economics_calendar` -> `trading_economics_calendar_event` (optional)
- `option_activity_events` -> `option_activity_event` (optional)
- `equity_abnormal_activity_events` -> `equity_abnormal_activity_event` (optional)

## Output

`saved/event_overlay_model_inputs.csv`
