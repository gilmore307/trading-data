# Context

## Why This Repository Exists

The trading system depends on reliable upstream data. Data collection and normalization are intentionally isolated in `trading-data` so that downstream strategy, model, execution, and dashboard repositories consume documented outputs instead of provider-specific implementation details.

`trading-data` provides the component boundary between external data providers and the rest of the trading platform.

## Related Systems

| System | Relationship |
|---|---|
| `trading-main` | Owns global architecture, registry, templates, shared helpers, and cross-repository contracts. |
| `trading-manager` | Sends or schedules structured data requests and consumes manifests/ready signals for lifecycle decisions. |
| `trading-storage` | Owns durable storage layout, retention, archive, backup, restore, and artifact placement rules. |
| `trading-strategy` | Consumes approved data artifacts for strategy research and backtesting. |
| `trading-model` | Consumes market/data artifacts for market-state research and later evaluation flows. |
| `trading-dashboard` | Displays already-produced data outputs and metadata; it should not become a data source of truth. |


## Data Domains

`trading-data` currently organizes data requests into three purpose-driven domains:

- market board data / 盘面数据: data collected to study broad market-board or market-regime conditions;
- instrument data / 标的数据: data collected to study a specific tradable symbol or instrument;
- option data / 期权数据: data collected to study options conditions for a specific underlying.

These domains correspond to later model lanes, but `trading-data` only owns data acquisition, cleaning, and output production. Model design, labels, training, and inference belong in `trading-model`.

See `docs/07_data_domains.md`.

## Expected External Interfaces

Potential external interfaces include:

- market data APIs;
- instrument/reference data APIs;
- options data APIs;
- macroeconomic data APIs;
- market calendars and holiday schedules;
- symbol/reference-data providers;
- local or shared storage through `trading-storage` contracts.

Specific provider choices, secret aliases, credentials, quotas, retry expectations, and commercial limits are not settled yet. See `docs/08_data_sources.md` for the source-connection boundary.

## Environment

Development is server-hosted under `/root/projects/trading-data`.

The shared Python environment is anchored by `trading-main` at:

```text
/root/projects/trading-main/.venv
```

`trading-data` should not create an independent virtual environment unless a documented exception is accepted.

US Eastern time is the default project planning time. Data contracts may require UTC timestamps for artifact content; exact timestamp rules remain an open contract detail.

## Dependencies

Current system-level dependencies:

- `trading-main/docs/08_registry.md` for registry operating rules;
- `trading-main/templates/contracts/` for artifact, manifest, ready-signal, and request drafting templates;
- `trading-main/helpers/` for approved shared helper surfaces;
- `trading-storage` for persistent layout and retention contracts;
- external data providers once chosen.

## Global Registration Discipline

If data work introduces a name that other repositories may consume, route it back to `trading-main` before treating it as stable.

This includes:

- shared data fields;
- artifact, manifest, ready-signal, or request type values;
- global helper methods;
- reusable templates;
- status values;
- repository-wide config keys;
- provider-independent terminology.

Temporary names may appear in local drafts, but they must be recorded and reviewed before becoming cross-repository contracts.

## Important Constraints

- Do not store generated datasets in Git.
- Do not store API keys, credentials, or tokens in Git.
- Keep provider-specific quirks documented close to provider integration work once implementation exists.
- Keep downstream strategy/model interpretation out of this repository.
- Prefer fixture-backed provider tests before live provider calls.
- Respect provider quotas and rate limits; do not build tight unaudited polling loops.
- Exact artifact, manifest, request, and ready-signal schemas remain open until accepted through `trading-main` contracts.
