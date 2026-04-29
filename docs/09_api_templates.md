# API Templates

`trading-source` should design each historical acquisition feed from the API/source requirements before writing connector code.

Reusable template files live in `trading-main/templates/data_tasks/`. This file explains how `trading-source` should apply them to API-specific feeds and manager-facing sources.

## Template Sources

| Template | Use |
|---|---|
| `templates/data_tasks/task_key.json` | Draft the manager-issued task key shape for a feed/source. |
| `templates/data_tasks/source_readme.md` | Draft the source README and boundary. |
| `templates/data_tasks/pipeline.py` | Default single-file feed/source implementation template. |
| `templates/data_tasks/fetch_spec.md` | Capture API/source fetch requirements. |
| `templates/data_tasks/clean_spec.md` | Capture normalization and validation-prep requirements. |
| `templates/data_tasks/save_spec.md` | Capture development-save layout and future durable mapping. |
| `templates/data_tasks/completion_receipt.json` | Draft success/failure receipt evidence. |
| `templates/data_tasks/fixture_policy.md` | Capture fixture, mock, and live-call guardrails. |

These templates are drafts, not accepted schemas. Stable field names, statuses, task types, receipt shapes, and storage contracts still require `trading-main` registry/contract review.

Accepted acquisition feed names belong in the `trading-main` registry as `kind=data_feed`; manager-facing source outputs belong as `kind=data_source`, not as generic terminology rows.

## Runtime JSON Minimalism

`task_key.json` and `completion_receipt.json` should stay small. Add a field only when manager, runner, feed/source code, or receipt readers actually consume it. Provider documentation URLs, explanatory notes, and source research details belong in registry rows, provider docs, or the source README, not runtime JSON.

A task key is stable across many invocations, including periodic or scheduled tasks. Per-run values do not belong in the task key; they belong in completion receipt `runs[]`.

## Source Design Order

For each data source, design in this order:

1. Identify the API/source endpoint, official docs, credentials/no-key rule, and source-of-truth page in the source README/specs.
2. Fill the fetch spec from the provider's concrete API requirements.
3. Fill the clean spec from the raw response shape and target normalized outputs.
4. Fill the save spec for development files under `TRADING_SOURCE_DEVELOPMENT_STORAGE_ROOT`.
5. Fill the completion receipt template for both success and failure evidence.
6. Fill the fixture policy before writing default tests.
7. Only then create `pipeline.py` under the accepted source package layout.

## Future Source Folder Shape

When implementation starts, each feed should eventually have a folder like:

```text
src/data_feed/<feed>/
  README.md
  pipeline.py
```

`pipeline.py` should expose one public `run(task_key, run_id=...)` entry point and keep four internal step functions:

- `fetch(...)` retrieves source data and writes raw development files.
- `clean(...)` normalizes raw files into cleaned outputs.
- `save(...)` writes development outputs under `storage/`; durable SQL waits for storage contracts.
- `write_receipt(...)` emits success/failure completion receipts.

A shared runner should call feed/source `run(...)` from a task key so `trading-manager` does not need to know feed/source internals. Split the step functions into separate modules only when a feed/source becomes too large for one file.

## API-Specific Checklist

Every feed/source design should answer:

- Which API endpoint(s), URL pattern, or local terminal command is used?
- Which task key fields are required?
- Which credentials or no-key rule applies?
- What request parameters are accepted and rejected?
- How are pagination, retries, and rate limits handled?
- What timezone and timestamp semantics does the source use?
- What historical range limits or snapshot semantics apply?
- What raw files are produced transiently, if any? High-volume trade/quote raw rows should normally be stream/segment inputs only, not saved outputs.
- What cleaned/aggregated outputs are produced? For high-volume market microstructure data, default persisted outputs should be ET-aligned aggregates rather than raw rows.
- What files are saved under `storage/<task-id>/runs/<run-id>/`?
- What run receipt fields prove success or failure?
- Which fixtures cover expected and edge-case responses?

## Feed-Specific Notes

Initial feed planning names remain:

- `01_feed_alpaca_bars`
- `02_feed_alpaca_liquidity`
- `03_feed_alpaca_news`
- `10_feed_thetadata_option_primary_tracking`
- `11_feed_thetadata_option_event_timeline`
- `09_feed_thetadata_option_selection_snapshot`
- `04_feed_okx_crypto_market_data`
- `07_feed_trading_economics_calendar_web`
- `calendar_discovery`
- `06_feed_etf_holdings`
- `08_feed_sec_company_financials`


ThetaData option acquisition is intentionally split by use case, not endpoint family:

- `10_feed_thetadata_option_primary_tracking` supplements equity bars/liquidity by selecting one primary option contract and tracking it at the same research grain.
- `11_feed_thetadata_option_event_timeline` produces news-like timestamped option activity events.
- `09_feed_thetadata_option_selection_snapshot` captures point-in-time option-chain information visible when an equity signal needs to choose a contract.

`macro_data` has been removed as an executable macro acquisition feed. Macro model inputs now use the conservative `07_feed_trading_economics_calendar_web` visible-page interface; official macro API secret aliases may remain stored but are not active manager task routes.

`08_feed_sec_company_financials` covers company financial report data from official SEC EDGAR APIs. It should use SEC-specific task/run ID prefixes such as `08_feed_sec_company_financials_task_...` and `08_feed_sec_company_financials_run_...`, preserve all stock-research timestamps in America/New_York, and persist only final cleaned development outputs rather than bulky raw SEC responses.

## Implemented feed CLIs

- `trading-source-01-feed-alpaca-bars` / `python -m data_feed.01_feed_alpaca_bars` runs the Alpaca bars pipeline.
- `trading-source-02-feed-alpaca-liquidity` / `python -m data_feed.02_feed_alpaca_liquidity` runs the aggregate-only Alpaca liquidity pipeline.
- `trading-source-03-feed-alpaca-news` / `python -m data_feed.03_feed_alpaca_news` runs the Alpaca news pipeline.
- `trading-source-04-feed-okx-crypto-market-data` / `python -m data_feed.04_feed_okx_crypto_market_data` runs the OKX crypto bar/trade/liquidity pipeline.
