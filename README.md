# trading-data

`trading-data` is the unified data-production repository for the trading system.

It owns historical market, options, issuer, filing, news, calendar, and related provider data acquisition, cleaning, validation, and publication for downstream repositories. It executes self-contained task key files from the `trading-manager` control plane; legacy source pipelines may still create ignored local files under runtime `storage/`, while accepted SQL-only source outputs write directly to reviewed SQL tables.

It does not own shared storage policy, model training/evaluation labels, strategy/backtest generation, model research, execution, dashboard rendering, secrets, credentials, notebooks, or generated data committed to Git.

## Top-Level Structure

```text
docs/        Required docs spine plus component-specific guides for feed, source, and feature organization.
src/         Importable data-feed, data-source, data-feature, storage, and probe implementation packages.
tests/       First-party tests for data-feed pipelines, interface probes, storage, and sources.
```

Executable CLIs are package entrypoints that call `src/`. If future operational wrappers are needed, place them under `scripts/`; `src/` must not import `scripts/`.

## Docs Set

```text
docs/
  00_scope.md
  01_context.md
  02_layer_01_market_regime.md
  03_layer_02_sector_context.md
  04_layer_03_target_state_vector.md
  80_task.md
  81_decision.md
  82_memory.md
  90_data_organization.md
  91_data_feed.md
  92_api_templates.md
  93_feed_availability.md
  94_model_inputs.md
  95_data_stack_closeout.md
```

## Input And Output

Input: self-contained historical data task key files from the `trading-manager` control plane once the task-key contract is accepted.

Development output: local SQL databases and, for legacy source pipelines, inspected local files and task completion receipts under runtime-created `storage/` (ignored by Git).

Durable output: storage-backed SQL/artifact outputs plus manifests and ready signals as cross-repository contracts are accepted.

`trading-data` owns the data chain from provider feeds to model-scoped sources to deterministic point-in-time feature tables. For high-dimensional generated feature surfaces such as `feature_01_market_regime`, SQL storage may use one row per point-in-time key with generated feature values inside JSONB payloads instead of one physical column per feature. Request-driven Layer 3 target state-vector production (`feature_03_target_state_vector`) also belongs here as deterministic feature production; state-label design, model training, evaluation, and promotion decisions belong to `trading-model`. Realtime execution feeds belong to `trading-execution`.

## Data Organization

`trading-data` now organizes work around provider/feed adapters, model-scoped source tables, deterministic feature tables, and accepted SQL outputs. The old market-board / instrument / option domain labels remain historical planning language, not the primary runtime or docs boundary.

See `docs/90_data_organization.md`. API-specific source design guidance is in `docs/92_api_templates.md`; model-layer mapping is in `docs/94_model_inputs.md`; current repository closeout is in `docs/95_data_stack_closeout.md`. Current layer-specific data workflows, boundaries, and acceptance gates live in `docs/02_layer_01_market_regime.md`, `docs/03_layer_02_sector_context.md`, and `docs/04_layer_03_target_state_vector.md`.

## Platform Dependencies

- `trading-manager` owns global contracts, registry, shared helpers, and templates.
- `trading-storage` owns durable storage layout, retention, archive, backup, and restore rules.
- `trading-manager` owns control-plane scheduling, request generation, lifecycle, retries, and promotion decisions.

Any new global helper, template, shared field, status, type, or reusable vocabulary discovered while developing `trading-data` must be routed back to `trading-manager` for documentation and registry review before other repositories depend on it.
