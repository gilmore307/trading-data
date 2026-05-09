# scripts

Thin executable wrappers for `trading-data`.

Reusable implementation belongs in `src/`. A script may import `src` code and pass through CLI arguments, but it should not own business logic, contracts, or source-specific behavior.

## Files

- `generate_feature_01_market_regime.py` — wrapper for `data_feature.feature_01_market_regime.sql`.
- `generate_feature_02_sector_context.py` — wrapper for `data_feature.feature_02_sector_context.sql`.
- `generate_feature_03_target_state_vector.py` — wrapper for `data_feature.feature_03_target_state_vector.sql`.
- `generate_feature_04_event_overlay.py` — wrapper for `data_feature.feature_04_event_overlay.sql`.
- `generate_feature_08_option_expression.py` — wrapper for `data_feature.feature_08_option_expression.sql`.

Installed package entrypoints in `pyproject.toml` remain the preferred package CLI surface for feeds, sources, and features. The `scripts/generate_feature_*.py` wrappers provide a complete repo-local operational surface for accepted `trading-data` feature tables.

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
