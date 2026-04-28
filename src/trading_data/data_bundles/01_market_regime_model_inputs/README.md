# 01_market_regime_model_inputs

MarketRegimeModel manager-facing model-input manifest bundle.

This bundle does not fetch provider data. It receives a manager task key that points at already-saved source artifacts, validates those paths against the bundle-local input contract, and writes a point-in-time manifest CSV for the MarketRegimeModel layer.

## Input parameters

The manager supplies these values in `task_key.params`:

- `as_of` — required. America/New_York point-in-time timestamp for the manifest. Legacy `as_of_et` and `available_time` are accepted by the shared runner as compatibility aliases.
- `input_paths` — required object. Keys are configured input roles; each value is one path string or a list of path strings.
- `config_path` — optional reviewed override for `config.json`; normal runs use this directory's bundle-local config.

Minimum valid `input_paths` roles:

- `broad_market_bars`
- `sector_etf_bars`

Optional `input_paths` roles:

- `cross_asset_etf_bars`

The task key also carries orchestration fields outside `params`, including `task_id`, `bundle = "01_market_regime_model_inputs"`, and optional `output_root`.

## Config

`config.json` owns stable contract facts required to complete the task but not supplied per run:

- `version` — config schema/version marker.
- `description` — human-readable contract summary.
- `model_id = "market_regime_model"` — target model layer.
- `inputs` — ordered role contract used to build output rows:
  - `role` — manifest input role name expected under `params.input_paths`.
  - `data_kind` — expected upstream data kind for that role.
  - `required` — whether the role must be present in the task key.
  - `notes` — role-specific contract notes copied into the manifest.

## Output format

Final saved artifact:

```text
<output_root>/runs/<run_id>/saved/01_market_regime_model_inputs.csv
```

Columns, in order:

1. `bundle`
2. `model_id`
3. `as_of`
4. `input_role`
5. `data_kind`
6. `path`
7. `required`
8. `point_in_time`
9. `notes`

Natural grain: one row per configured input role/path at the requested `as_of`. Optional roles with no paths still emit an empty-path row marked `required=false`.

Run metadata:

- cleaned JSONL: `<output_root>/runs/<run_id>/cleaned/01_market_regime_model_inputs.jsonl`
- cleaned schema: `<output_root>/runs/<run_id>/cleaned/schema.json`
- request manifest: `<output_root>/runs/<run_id>/request_manifest.json`
- completion receipt: `<output_root>/completion_receipt.json`
