# Data Stack Closeout

Status: accepted repository closeout for current data-source/model-input design phase
Date: 2026-05-08

## Closeout scope

`trading-data` has a complete accepted local feed/source/feature implementation surface for the current Layers 1-8 model-input route.

| Surface | Current owner path | Closeout state |
|---|---|---|
| Feed availability inventory | `src/feed_availability/`, `src/feed_interfaces/` | accepted probe/catalog support; live smoke remains opt-in |
| Alpaca bars/liquidity/news | `src/data_feed/01_*`, `02_*`, `03_*` | accepted feeds with fixture-safe tests and no default raw persistence |
| OKX crypto market data | `src/data_feed/04_feed_okx_crypto_market_data/` | accepted feed/catalog surface |
| GDELT / ETF holdings / Trading Economics / SEC feeds | `src/data_feed/05_*` through `08_*` | accepted feed surfaces for current source planning |
| ThetaData option feeds | `src/data_feed/09_*` through `11_*` | accepted local terminal-oriented V1 feeds for option snapshot, primary tracking, and event timeline |
| Layer 1 data | `source_01_market_regime`, `feature_01_market_regime` | accepted market-regime input/feature surfaces |
| Layer 2 data | `feature_02_sector_context` | accepted sector-context feature surface; no dedicated Layer 2 source package |
| Layer 3 data | `source_02_target_candidate_holdings`, `source_03_target_state`, `feature_03_target_state_vector` | accepted target-candidate preparation, target-state observed-input, and feature-block surfaces |
| Layer 4 data | `source_04_event_overlay`, `feature_04_event_overlay` plus event sub-sources | accepted event overview/index and deterministic event-feature boundary with canonical dedup fields |
| Layer 5 data | no dedicated `trading-data` source or feature | accepted no-new-source/no-feature boundary; alpha confidence belongs to `trading-model` |
| Layer 6 data | no dedicated `trading-data` source or feature | accepted no-new-source/no-feature boundary; position projection belongs to `trading-model` / control-plane state |
| Layer 7 data | no dedicated `trading-data` source or feature | accepted no-new-source/no-feature boundary; underlying action belongs outside `trading-data` |
| Layer 8 data | `source_05_option_expression`, `feature_08_option_expression`, `source_06_position_execution` | accepted option-expression source, deterministic option-candidate feature, and selected-contract tracking boundaries |

This closes the current data-design/model-input phase. It does not approve unattended production data orchestration or final durable storage contracts.

## Freshness and model-standard closeout

Two previously active hardening items are now resolved as conservative closeout rules:

1. ETF holdings / target-candidate preparation must preserve point-in-time visibility. If no explicit `available_time` is supplied, `source_02_target_candidate_holdings` now defaults holdings rows to the next regular US session open after `as_of_date` (`09:30 America/New_York`, skipping weekends). Same-day availability requires explicit source evidence or reviewed task input.
2. `equity_abnormal_activity_event` now uses the explicit default `model_standard = equity_abnormal_activity_conservative_v1` with `calibration_status = conservative_fixture_default_not_production_calibrated`. The default may produce conservative event evidence, but production training labels or promoted gates still require a reviewed historical calibration report.

## Remaining work classification

Remaining items are production hardening / manager-storage orchestration, not open data-stack design blockers. The non-data-accumulation policy layer is defined in `docs/96_production_hardening.md`; remaining implementation work is narrower:

- physical manager/storage queue and SQL/storage implementation for `manager_request_v1`, `run_manifest_v1`, `artifact_ref_v1`, and `ready_signal_v1`;
- production packaging/service decisions beyond the implemented local source slices;
- source-specific parameter dictionaries and broader production coverage source files;
- optionability summary promotion after the model/control-plane contract needs it;
- optional ThetaData service/autostart setup if unattended option data runs become accepted;
- production calibration reports for data-derived event standards before labels depend on them.

## Boundary closeout

`trading-data` owns source acquisition, deterministic source-backed feature construction, point-in-time data visibility, and local development receipts. It does not own model promotion decisions, model labels/evaluation, broker execution, production scheduling/lifecycle retries, or final storage retention policy.

Production orchestration now belongs to the manager/control-plane phase, with durable storage details coordinated through `trading-storage`.
