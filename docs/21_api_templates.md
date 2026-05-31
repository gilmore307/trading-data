# API Templates

Design each acquisition/source route before writing connector code.

Reusable starter templates live in `trading-storage/main/templates/data_tasks/`; `trading-manager` owns review, registry, and contract promotion for shared template vocabulary. They help shape local source design; they are parked drafts unless the owning docs and registry explicitly accept a concrete contract.

## Template Sources

| Template | Use |
|---|---|
| `task_key.json` | Starter manager-issued task/request shape. |
| `source_readme.md` | Starter source boundary and operator notes. |
| `pipeline.py` | Default single-file feed/source implementation shape. |
| `fetch_spec.md` | API/source request requirements. |
| `clean_spec.md` | Normalization and validation-prep requirements. |
| `save_spec.md` | Local development output and reviewed handoff mapping. |
| `completion_receipt.json` | Success/failure evidence shape. |
| `fixture_policy.md` | Fixture, mock, and provider-call guardrails. |

Stable fields, statuses, task types, receipt shapes, artifact refs, and storage contracts require `trading-manager` / `trading-storage` review.

## Design Order

For each feed/source:

1. Identify the official endpoint/source page, credential/no-key rule, and source-of-truth note.
2. Define required and optional task/request parameters.
3. Document pagination, retries, rate limits, timeouts, and entitlement behavior.
4. Define timestamp/timezone semantics.
5. Define raw/transient handling and final cleaned outputs.
6. Define SQL table or reviewed artifact handoff.
7. Define receipt/manifest evidence for success and failure.
8. Define fixture-safe tests and provider-call guardrails.
9. Implement `pipeline.py` under the accepted package path.

## Runtime JSON Minimalism

Task/request JSON and receipts should stay small. Add a field only when manager, runner, feed/source code, manifest writers, or receipt readers consume it.

Do not place provider docs, long notes, or source research inside runtime JSON. Put that material in registry rows, provider docs, source READMEs, or specs.

Stable task/request values belong in the task/request file. Per-run evidence belongs in receipts/manifests.

## Package Shape

A feed package should look like:

```text
src/data_feed/<feed>/
  README.md
  __main__.py
  pipeline.py
```

A manager-facing source package should look like:

```text
src/data_source/<source>/
  README.md
  __main__.py
  pipeline.py
```

`pipeline.py` should keep the route easy to inspect:

- `fetch(...)` retrieves provider/source evidence;
- `clean(...)` normalizes rows;
- `save(...)` writes accepted SQL/artifact outputs or storage-owned development evidence;
- `write_receipt(...)` emits sanitized run evidence.

Split into more modules only when one file becomes harder to audit than the split.

## Feed Names

Current accepted feed package names:

- `01_feed_alpaca_bars`
- `02_feed_alpaca_liquidity`
- `03_feed_alpaca_news`
- `04_feed_okx_crypto_market_data`
- `05_feed_gdelt_news`
- `06_feed_etf_holdings`
- `07_feed_trading_economics_calendar_web`
- `08_feed_sec_company_financials`
- `09_feed_thetadata_option_selection_snapshot`
- `10_feed_thetadata_option_primary_tracking`
- `11_feed_thetadata_option_event_timeline`

ThetaData option acquisition is split by use case:

- selection snapshot: point-in-time chain/contract visibility;
- primary tracking: bars for one supplied contract;
- event timeline: timestamped option activity events for one supplied contract and standard.

`macro_data` is not an active executable feed. Trading Economics macro source rows are retained in `trading-storage/storage/01_source_data/monthly_backfill/trading_economics_calendar_web`; the expired website route is not an active model-input acquisition path.

## Implemented CLIs

Feed CLIs are declared in `pyproject.toml` and mirror package modules, for example:

```bash
trading-data-01-feed-alpaca-bars
PYTHONPATH=src python3 -m data_feed.01_feed_alpaca_bars
```

Source and feature CLIs follow the same rule:

```bash
trading-data-m01-market-regime-data-acquisition
trading-data-m01-market-regime-feature-generation
```

Reusable logic belongs in `src/`. Stable callable surfaces should use package CLIs declared in `pyproject.toml`; reviewed `scripts/` wrappers may exist only as thin operational entrypoints over package code or bounded task-key builders, such as deployed maintenance refresh commands.
