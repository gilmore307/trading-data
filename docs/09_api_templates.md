# API Templates

`trading-data` should design each historical acquisition bundle from the API/source requirements before writing connector code.

Reusable template files live in `trading-main/templates/data_tasks/`. This file explains how `trading-data` should apply them to API-specific bundles.

## Template Sources

| Template | Use |
|---|---|
| `templates/data_tasks/task_key.json` | Draft the manager-issued task key shape for a bundle. |
| `templates/data_tasks/bundle_readme.md` | Draft the bundle README and boundary. |
| `templates/data_tasks/pipeline.py` | Default single-file bundle implementation template. |
| `templates/data_tasks/fetch_spec.md` | Capture API/source fetch requirements. |
| `templates/data_tasks/clean_spec.md` | Capture normalization and validation-prep requirements. |
| `templates/data_tasks/save_spec.md` | Capture development-save layout and future durable mapping. |
| `templates/data_tasks/completion_receipt.json` | Draft success/failure receipt evidence. |
| `templates/data_tasks/fixture_policy.md` | Capture fixture, mock, and live-call guardrails. |

These templates are drafts, not accepted schemas. Stable field names, statuses, task types, receipt shapes, and storage contracts still require `trading-main` registry/contract review.

## Bundle Design Order

For each source bundle, design in this order:

1. Identify the API/source endpoint, official docs, credentials/no-key rule, and source-of-truth page.
2. Fill the fetch spec from the provider's concrete API requirements.
3. Fill the clean spec from the raw response shape and target normalized outputs.
4. Fill the save spec for development files under `TRADING_DATA_DEVELOPMENT_STORAGE_ROOT`.
5. Fill the completion receipt template for both success and failure evidence.
6. Fill the fixture policy before writing default tests.
7. Only then create `pipeline.py` under the accepted source package layout.

## Future Source Folder Shape

When implementation starts, each bundle should eventually have a folder like:

```text
src/trading_data/data_sources/<bundle>/
  README.md
  pipeline.py
```

`pipeline.py` should expose one public `run(...)` entry point and keep four internal step functions:

- `fetch(...)` retrieves source data and writes raw development files.
- `clean(...)` normalizes raw files into cleaned outputs.
- `save(...)` writes development outputs under `data/storage/`; durable SQL waits for storage contracts.
- `write_receipt(...)` emits success/failure completion receipts.

A shared runner should call bundle `run(...)` from a task key so `trading-manager` does not need to know bundle internals. Split the step functions into separate modules only when a bundle becomes too large for one file.

## API-Specific Checklist

Every bundle design should answer:

- Which API endpoint(s), URL pattern, or local terminal command is used?
- Which task key fields are required?
- Which credentials or no-key rule applies?
- What request parameters are accepted and rejected?
- How are pagination, retries, and rate limits handled?
- What timezone and timestamp semantics does the source use?
- What historical range limits or snapshot semantics apply?
- What raw files are produced?
- What cleaned outputs are produced?
- What files are saved under `data/storage/<task-or-run-id>/`?
- What receipt fields prove success, partial success, or failure?
- Which fixtures cover expected and edge-case responses?

## Bundle-Specific Notes

Initial bundle planning names remain:

- `alpaca_bars`
- `alpaca_market_events`
- `thetadata_option_1m_bundle`
- `thetadata_option_snapshot_bundle`
- `okx_bars`
- `macro_release_<release_key>`
- `calendar_discovery`
- `etf_holdings`

Macro bundles must be split by release event or release family, not grouped merely because they are macro data.
