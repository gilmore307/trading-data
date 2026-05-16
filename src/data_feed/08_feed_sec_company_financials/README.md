# 08_feed_sec_company_financials feed

`08_feed_sec_company_financials` fetches official SEC EDGAR JSON APIs for public-company filing metadata and XBRL facts. It is a historical data feed for `trading-data`.

Run a task key with:

```bash
PYTHONPATH=src python3 -m data_feed.08_feed_sec_company_financials path/to/task_key.json --run-id 08_feed_sec_company_financials_run_<id>
```

Supported `params.data_kind` values:

- `sec_submission` — SEC submissions filing-history JSON for one CIK.
- `sec_company_fact` — all companyfacts for one CIK, optionally filtered by `taxonomy`, `tag`, and `unit`.
- `sec_company_concept` — one taxonomy/tag concept for one CIK.
- `sec_xbrl_frame` — one XBRL frame across companies.
- `sec_filing_document` — one official SEC filing document by CIK, accession number, and document name; saves compact metadata plus a local text artifact for reviewed downstream interpretation.

Common params:

- `cik` — required except for `sec_xbrl_frame`.
- `taxonomy` — defaults to `us-gaap` where applicable.
- `tag` — required for company concept and frame requests; optional filter for companyfacts.
- `unit` — optional, default `USD` for frames.
- `frame` — required for frame requests, e.g. `CY2023Q4I`.
- `accession_number` and `document_name` — required for `sec_filing_document`.

Outputs:

- `request_manifest.json` — endpoint, sanitized request params, fetch time, and fair-access evidence.
- `cleaned/<data_kind>.jsonl` and `cleaned/schema.json` — transient run-local normalized rows.
- `saved/<data_kind>.csv` — final compact CSV output.
- `saved/sec_filing_document_text.txt` — final official filing text artifact for `sec_filing_document` only.
- `completion_receipt.json` at task root.

Rules:

- Use official SEC endpoints only by default.
- Automated requests must send an identifying SEC User-Agent.
- Full raw SEC JSON responses are not persisted by default because `companyfacts` can be large.
- `sec_filing_document` is the explicit exception: the requested official document text is persisted as a reviewed artifact because downstream guidance/result interpretation needs source text and provenance.
- This feed does not normalize GAAP facts into model-ready financial statements; that belongs to a reviewed model/financials transformation boundary.
