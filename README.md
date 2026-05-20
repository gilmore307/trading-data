# trading-data

`trading-data` is the trading system's data-production repository.

It acquires provider data, normalizes it into reviewed source tables/artifacts, derives deterministic feature tables, and hands ready outputs to downstream repositories. The direct route is:

```text
provider/API/web/file -> data_feed -> data_source -> data_feature -> SQL/artifact handoff
```

It does not own model training, promotion, strategy/backtest logic, broker execution, dashboard rendering, global storage policy, or secrets.

## Top-Level Structure

```text
docs/        Repository boundary, data routes, source/feed rules, and acceptance notes.
src/         Importable feed, source, feature, layer-catalog, storage, and probe packages.
tests/       Fixture-safe tests for feeds, sources, features, storage, and probes.
```

## Current Route

- `data_feed` talks to one provider/API/web/file family and produces normalized feed-level evidence.
- `data_source` accepts a manager-issued task/request, composes feed evidence, and writes reviewed model-input source outputs.
- `data_feature` derives deterministic layer-ready feature blocks from accepted source outputs.
- `data_layers` catalogs the Layer 1-10 `trading-data` ownership surface so docs/src/CLI/tests stay aligned.
- `storage` provides low-level persistence helpers; durable layout and retention remain `trading-storage` responsibilities.

Accepted SQL outputs are the preferred model-input boundary. Local ignored `storage/` files are development evidence, not durable interfaces. `source_NN_*` numbers identify accepted source contracts; they do not necessarily equal model layer numbers.

## Key Docs

- `docs/00_scope.md` — repository purpose and boundaries.
- `docs/02_architecture.md` — feed/source/feature organization.
- `docs/20_data_feed.md` — provider and feed rules.
- `docs/21_api_templates.md` — task/source design order.
- `docs/22_feed_availability.md` — provider/data-kind availability inventory.
- `docs/10_layer_01_market_regime.md` through `docs/19_layer_10_event_risk_governor.md` — layer-specific data boundaries.
- `docs/30_model_inputs.md` — mapping from data outputs to model layers.
- `docs/03_contracts.md` — accepted local data-stack acceptance.
- `docs/40_production_hardening.md` — non-production hardening contracts.

## Platform Boundaries

- `trading-manager` owns registry names, task/request contracts, scheduling, approvals, retries, and promotion control.
- `trading-storage` owns durable layout, manifests, artifact references, ready signals, retention, backup, and restore.
- `trading-model` owns labels, training, evaluation, and promotion evidence.
- `trading-execution` owns realtime execution-time data and broker mutation.

Reusable names, fields, statuses, helpers, templates, and cross-repository contracts discovered here must be routed through `trading-manager` before other repositories depend on them.

## Verification

Run the full fixture-safe suite with top-level discovery plus explicit feed/source/interface subdirectory discovery; see `tests/README.md` for the exact command list.
