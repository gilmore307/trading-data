# scripts

Thin executable maintenance and operational wrappers for `trading-data`.

Reusable implementation belongs in `src/`. A script may import `src` code and pass through CLI arguments, but it should not own business logic, contracts, or source-specific behavior.

## Current posture

`trading-data` feature generation does not keep duplicate `scripts/generate_feature_*.py` wrappers. Feature implementations live under `src/data_feature/`, and their stable callable CLI surface is the package entrypoint declared in `pyproject.toml`:

- `trading-data-feature-01-market-regime`
- `trading-data-feature-02-sector-context`
- `trading-data-feature-03-target-state-vector`
- `trading-data-feature-04-event-overlay`
- `trading-data-feature-08-option-expression`

This keeps one implementation surface (`src/data_feature/`) and one package CLI surface (`pyproject.toml`) instead of maintaining parallel script wrappers.

## Layer CLI posture

| Layer | `trading-data` CLI surface |
|---|---|
| 1 Market Regime | `trading-data-source-01-market-regime`, `trading-data-feature-01-market-regime` |
| 2 Sector Context | `trading-data-feature-02-sector-context` |
| 3 Target State Vector | `trading-data-source-02-target-candidate-holdings`, `trading-data-source-03-target-state`, `trading-data-feature-03-target-state-vector` |
| 4 Event Overlay | `trading-data-source-04-event-overlay`, `trading-data-feature-04-event-overlay` |
| 5 Alpha Confidence | No dedicated `trading-data` CLI; model/evaluation boundary owns it. |
| 6 Position Projection | No dedicated `trading-data` CLI; position/risk/control-plane boundary owns it. |
| 7 Underlying Action | No dedicated `trading-data` CLI; action selection belongs outside this repo. |
| 8 Option Expression | `trading-data-source-05-option-expression`, `trading-data-source-06-position-execution`, `trading-data-feature-08-option-expression`, and ThetaData option feed CLIs `09`-`11`. |

The authoritative layer-to-structure mapping is `src/data_layers/catalog.py`; tests enforce it.
