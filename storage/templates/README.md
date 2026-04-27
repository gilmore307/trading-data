# Templates

Maintained templates and concrete output previews for `trading-data`.

Preview CSV/JSON files under `data_kinds/` are generated materialized output templates. Do not hand-edit those preview files; edit the registry-id based generator at `src/trading_data/template_generators/data_kind_previews.py`, then regenerate them.

```bash
PYTHONPATH=src python3 -m trading_data.template_generators.data_kind_previews
```

Use `--check` in validation to confirm committed previews match generated output.

## Subdirectories

- `data_kinds/` — source-organized final saved data-kind catalog plus small CSV preview templates for each accepted final data kind.
