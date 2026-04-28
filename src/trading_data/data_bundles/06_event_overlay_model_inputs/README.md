# 06_event_overlay_model_inputs

Manager-facing EventOverlayModel input bundle.

This bundle accepts a manager task key, loads bundle-local `config.json`, writes point-in-time artifact references, and saves the final bundle manifest to SQL table `model_inputs.model_input_artifact_reference`. It does not fetch raw provider data directly; source acquisition remains in `trading_data.data_sources`.

## Input parameters

Required task key fields:

- `bundle`: `06_event_overlay_model_inputs`
- `task_id`: stable task identifier
- `params.as_of`: point-in-time timestamp for the model input view
- `params.input_paths`: object mapping configured input roles to one artifact reference or a list of artifact references

Optional task key fields:

- `params.config_path`: reviewed config override
- `output_root`: local receipt/request-manifest root

## Output

Final saved output is SQL-only:

```text
model_inputs.model_input_artifact_reference
```

Natural key:

```text
run_id + bundle + input_role + data_kind + artifact_reference
```

Columns:

- `run_id`
- `task_id`
- `bundle`
- `model_id`
- `as_of`
- `input_role`
- `data_kind`
- `artifact_reference`
- `required`
- `point_in_time`
- `notes`
- `created_at`

No saved bundle CSV is written.
