# 08_source_sec_company_financials bundle

`08_source_sec_company_financials` fetches official SEC EDGAR JSON APIs for public-company filing metadata and XBRL facts. It is a historical data bundle for `trading-data`.

Run a task key with:

```bash
PYTHONPATH=src python3 -m data_sources.08_source_sec_company_financials path/to/task_key.json --run-id 08_source_sec_company_financials_run_<id>
```

Supported `params.data_kind` values:

- `sec_submission` — SEC submissions filing-history JSON for one CIK.
- `sec_company_fact` — all companyfacts for one CIK, optionally filtered by `taxonomy`, `tag`, and `unit`.
- `sec_company_concept` — one taxonomy/tag concept for one CIK.
- `sec_xbrl_frame` — one XBRL frame across companies.

Common params:

- `cik` — required except for `sec_xbrl_frame`.
- `taxonomy` — defaults to `us-gaap` where applicable.
- `tag` — required for company concept and frame requests; optional filter for companyfacts.
- `unit` — optional, default `USD` for frames.
- `frame` — required for frame requests, e.g. `CY2023Q4I`.

Outputs:

- `request_manifest.json` — endpoint, sanitized request params, fetch time, and fair-access evidence.
- `cleaned/<data_kind>.jsonl` and `cleaned/schema.json` — transient run-local normalized rows.
- `saved/<data_kind>.csv` — final compact CSV output.
- `completion_receipt.json` at task root.

Rules:

- Use official SEC endpoints only by default.
- Automated requests must send an identifying SEC User-Agent.
- Full raw SEC responses are not persisted by default because `companyfacts` can be large.
- This bundle does not yet normalize GAAP facts into model-ready financial statements; that belongs to a later model/financials transformation layer.
