# Context

## Why This Repository Exists

The trading system needs reliable external observations. `trading-data` isolates provider/source acquisition and normalization so downstream repositories consume reviewed outputs instead of provider-specific implementation details.

The direct route is:

```text
provider/API/web/file -> data_feed -> data_source -> data_feature -> SQL/artifact handoff
```

## Related Systems

| System | Relationship |
|---|---|
| `trading-manager` | Owns registry, shared names, templates, request/control-plane policy, scheduling, approvals, retries, and promotion control. |
| `trading-storage` | Owns durable storage layout, manifests, artifact references, ready signals, retention, archive, backup, and restore. |
| `trading-model` | Consumes accepted data outputs and owns labels, samples, training, evaluation, model outputs, diagnostics, and promotion evidence. |
| `trading-execution` | Owns execution-time data, broker/account state, orders, and mutation. |
| `trading-dashboard` | Displays already-produced outputs and metadata; it is not a source of truth. |

## Data Organization

`trading-data` organizes work by feed/source/feature boundaries, not broad domain labels.

- `data_feed` acquires and normalizes provider/source evidence.
- `data_source` composes feeds into manager-facing model-input source outputs.
- `data_feature` builds deterministic point-in-time feature blocks from accepted source outputs.

See `docs/02_architecture.md` and `docs/30_model_inputs.md`.

## External Interfaces

Current provider/source surfaces include:

- Alpaca stock/ETF market data and news;
- ThetaData option data through local Terminal v3;
- OKX crypto market data;
- SEC EDGAR company filings/facts;
- ETF issuer holdings pages/files;
- Trading Economics visible macro calendar rows;
- official FOMC and macro release pages;
- optional reviewed official macro/economic APIs such as FRED, BLS, Census, BEA, and Treasury.

See `docs/20_data_feed.md` and `docs/22_feed_availability.md`.

## Environment

Development checkout is expected under the shared projects root, normally as the sibling repositories `trading-data`, `trading-manager`, and `trading-storage`. File artifacts and runtime evidence default to `trading-storage/storage/source_data/`. Runtime defaults can be overridden with `TRADING_DATA_REPO_ROOT`, `TRADING_PROJECTS_ROOT`, `TRADING_DATA_STORAGE_ROOT`, `TRADING_MANAGER_REGISTRY_CSV`, and `TRADING_STORAGE_REPO_ROOT`.

Use the shared trading Python environment unless a documented exception is accepted. US Eastern time is the default project planning and market-research timezone unless a storage/field contract states otherwise.

## Dependencies

- `trading-manager` registry and templates for shared names and request/receipt drafts.
- `trading-storage` contracts for durable manifests, artifact references, ready signals, and retention.
- External providers/source pages through explicitly guarded feed code.

## Registration Discipline

Route any cross-repository name through `trading-manager` before treating it as stable:

- fields;
- statuses;
- source/feed/data-kind names;
- artifact, manifest, ready-signal, and request type values;
- helper surfaces;
- templates;
- config keys;
- provider-independent terminology.

## Constraints

- Do not store generated datasets, raw dumps, logs, notebooks, credentials, or secrets in Git.
- Keep model labels, strategy/backtest logic, execution decisions, and dashboard interpretation out of this repository.
- Prefer fixture-backed tests before live provider calls.
- Respect quotas and rate limits; do not build unaudited polling loops.
- Do not create component-local `storage/` roots in this repository; route file artifacts through `trading-storage/storage/source_data/`.
