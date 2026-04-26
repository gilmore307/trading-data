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

Accepted acquisition bundle names belong in the `trading-main` registry as `kind=data_bundle`, not as generic terminology rows.

## Runtime JSON Minimalism

`task_key.json` and `completion_receipt.json` should stay small. Add a field only when manager, runner, bundle code, or receipt readers actually consume it. Provider documentation URLs, explanatory notes, and source research details belong in registry rows, provider docs, or the bundle README, not runtime JSON.

A task key is stable across many invocations, including periodic or scheduled tasks. Per-run values do not belong in the task key; they belong in completion receipt `runs[]`.

## Bundle Design Order

For each source bundle, design in this order:

1. Identify the API/source endpoint, official docs, credentials/no-key rule, and source-of-truth page in the bundle README/specs.
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

`pipeline.py` should expose one public `run(task_key, run_id=...)` entry point and keep four internal step functions:

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
- What raw files are produced transiently, if any? High-volume trade/quote raw rows should normally be stream/segment inputs only, not saved outputs.
- What cleaned/aggregated outputs are produced? For high-volume market microstructure data, default persisted outputs should be ET-aligned aggregates rather than raw rows.
- What files are saved under `data/storage/<task-id>/runs/<run-id>/`?
- What run receipt fields prove success or failure?
- Which fixtures cover expected and edge-case responses?

## Bundle-Specific Notes

Initial bundle planning names remain:

- `alpaca_bars`
- `alpaca_liquidity`
- `alpaca_news`
- `thetadata_option_primary_tracking`
- `thetadata_option_event_timeline`
- `thetadata_option_selection_snapshot`
- `okx_crypto_market_data`
- `macro_data`
- `calendar_discovery`
- `etf_holdings`
- `sec_company_financials`


ThetaData option acquisition is intentionally split by use case, not endpoint family:

- `thetadata_option_primary_tracking` supplements equity bars/liquidity by selecting one primary option contract and tracking it at the same research grain.
- `thetadata_option_event_timeline` produces news-like timestamped option activity events.
- `thetadata_option_selection_snapshot` captures point-in-time option-chain information visible when an equity signal needs to choose a contract.

`macro_data` is the single macro acquisition bundle. It stays clear by requiring task params to name the concrete provider/source, dataset/release/series, cadence, period, and output target. For source consistency, FRED should be used only for FRED/St. Louis Fed/ALFRED-unique data or explicitly approved FRED-native research series/groups, not as a duplicate path for official BLS/BEA/Census/Treasury data.

`sec_company_financials` covers company financial report data from official SEC EDGAR APIs. It should use SEC-specific task/run ID prefixes such as `sec_company_financials_task_...` and `sec_company_financials_run_...`, preserve all stock-research timestamps in America/New_York, and persist only final cleaned development outputs rather than bulky raw SEC responses.

## Implemented bundle CLIs

- `trading-data-alpaca-bars` / `python -m trading_data.data_sources.alpaca_bars` runs the Alpaca bars pipeline.
- `trading-data-alpaca-liquidity` / `python -m trading_data.data_sources.alpaca_liquidity` runs the aggregate-only Alpaca liquidity pipeline.
- `trading-data-alpaca-news` / `python -m trading_data.data_sources.alpaca_news` runs the Alpaca news pipeline.
- `trading-data-okx-crypto-market-data` / `python -m trading_data.data_sources.okx_crypto_market_data` runs the OKX crypto bar/trade/liquidity pipeline.
