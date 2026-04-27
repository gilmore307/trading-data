# macro_data bundle

`macro_data` is the parameterized macro acquisition bundle. Unlike the earlier
source-availability probes, this package performs real provider requests,
normalizes rows, and writes SQL-shaped macro release outputs.

Run a task key with:

```bash
PYTHONPATH=src python3 -m trading_data.data_sources.macro_data path/to/task_key.json --run-id macro_data_run_<id>
```

Supported `params.source` values now wired to actual API requests. Every task must also provide `release_time`; `effective_until` is optional and blank means latest known value. Use `metric` when the source response does not carry a suitable series id.


- `bls` — `series_ids`, optional `startyear`, `endyear`.
- `census` — `dataset`, `get`, optional `for`, `in`, `time`, `ucgid`, `predicates`.
- `bea` — `api_params` passed to BEA with `UserID` injected from `BEA_SECRET_ALIAS`/`/root/secrets/bea.json`.
- `us_treasury_fiscal_data` — `endpoint`, optional `api_params`.
- `fred` — `endpoint` (`series/observations`, `series/search`, or `series/vintagedates`), optional `series_id`, `api_params`.

Outputs are written under `output_root/runs/<run-id>/`:

- `request_manifest.json` — sanitized endpoint/request evidence; no full raw response.
- `cleaned/macro_release.jsonl` and `cleaned/schema.json` — normalized sparse release rows/schema.
- `saved/macro_release.csv` — SQL-shaped long-term output with `metric,release_time,effective_until,value`.
- `completion_receipt.json` at task root — per-run status, row counts, output references, and errors.

The bundle intentionally does not persist full raw/intermediate provider payloads
by default. Provider credentials stay under `/root/secrets` and only alias/key
metadata is written to manifests.
