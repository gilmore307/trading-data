# Contracts

Status: accepted repository acceptance for current data-source/model-input design phase
Date: 2026-05-08

## Acceptance scope

`trading-data` has a complete accepted local feed/source/feature implementation surface for the current ten-layer model-input route.

| Surface | Current owner path | Acceptance state |
|---|---|---|
| Feed availability inventory | `src/feed_availability/`, `src/feed_interfaces/` | accepted probe/catalog support; live smoke remains opt-in |
| Alpaca bars/liquidity/news | `src/data_feed/01_*`, `02_*`, `03_*` | accepted feeds with fixture-safe tests and no default raw persistence |
| OKX crypto market data | `src/data_feed/04_feed_okx_crypto_market_data/` | accepted feed/catalog surface |
| GDELT / ETF holdings / Trading Economics / SEC feeds | `src/data_feed/05_*` through `08_*` | accepted feed surfaces for current source planning |
| ThetaData option feeds | `src/data_feed/09_*` through `11_*` | accepted local terminal-oriented V1 feeds for option snapshot, primary tracking, and event timeline |
| Layer 1 data | `m01_market_regime_data_acquisition`, `m01_market_regime_feature_generation` | accepted market-regime input/feature surfaces |
| Layer 2 data | `m02_sector_context_feature_generation`, `m02_sector_context_data_acquisition` | accepted sector-context feature surface plus Layer 2-stage materialized target-candidate holdings handoff |
| Layer 3 data | `m03_target_state_vector_data_acquisition`, `m03_target_state_vector_feature_generation` | accepted target-state observed-input and feature-block surfaces; consumes Layer 2-stage candidate holdings |
| Layer 4 data | no dedicated `trading-data` source or feature | accepted no-new-source/no-feature boundary; EventFailureRiskModel consumes reviewed model/governance evidence, not raw source acquisition |
| Layer 5 data | no dedicated `trading-data` source or feature | accepted no-new-source/no-feature boundary; alpha confidence belongs to `trading-model` |
| Layer 6 data | no dedicated `trading-data` source or feature | accepted no-new-source/no-feature boundary; dynamic risk policy belongs to `trading-model` / control-plane / execution replay state |
| Layer 7 data | no dedicated `trading-data` source or feature | accepted no-new-source/no-feature boundary; position projection belongs to `trading-model` / control-plane state |
| Layer 8 data | no dedicated `trading-data` source or feature | accepted no-new-source/no-feature boundary; underlying action belongs outside `trading-data` |
| Layer 9 data | `m09_option_expression_data_acquisition`, `m09_option_expression_feature_generation`, `m09_option_expression_data_acquisition_contract_path` | accepted trading-guidance / option-expression data-acquisition, deterministic option-candidate feature-generation, and selected-contract market-path boundaries |
| Layer 10 data | `m10_event_risk_governor_data_acquisition`, `m10_event_risk_governor_feature_generation` plus event sub-sources | accepted event evidence/index and deterministic event-feature boundary with canonical dedup fields for event-risk-governor use |

This closes the current data-design/model-input phase. It does not approve unattended production data orchestration or final durable storage contracts.

## Machine-readable envelopes

Generic contract-envelope schemas live in `schemas/`:

- `task_key.schema.json`
- `completion_receipt.schema.json`
- `source_row.schema.json`
- `feature_row.schema.json`

These schemas define shared envelope fields only. Feed/source-specific payload fields remain owned by the corresponding module docs and tests until a reviewed registry-backed schema is accepted.

## Temporal Explorer Substrate

`trading-data` owns the provider-neutral calendar/timewheel SQL substrate used by dashboard, replay, and model-context inspection:

- `calendar_day`: one row per date from the accepted historical start, with timezone and day/month/quarter/year flags.
- `calendar_market_session`: venue-level session facts for NYSE, NASDAQ, and `CRYPTO_24_7`. Rule-generated NYSE/NASDAQ rows are marked `source_priority = inferred_rule`; official holiday/early-close sources may later override or enrich them.
- `chart_ohlcv_cache`: compact OHLCV visualization cache by symbol/timeframe/bucket. It supports dashboard Timewheel charts but is not a model-training or replay truth source.

The executable installer is `scripts/data/install_temporal_explorer_tables.py`. It may create tables and upsert deterministic day/session spine rows. It must not read `m10_event_risk_governor_data_acquisition`, treat raw Trading Economics storage rows as accepted Layer 10 events, call data providers, fabricate early closes, write raw news bodies, infer interpreted news refs, compute numeric surprises from string payloads, or infer chart bars without accepted source rows.

## Freshness and model-standard acceptance

Conservative acceptance rules:

1. ETF holdings / target-candidate preparation must preserve point-in-time visibility. If no explicit `available_time` is supplied, `m02_sector_context_data_acquisition` defaults holdings rows to the next regular US equity session open after `as_of_date` (`09:30 America/New_York`, skipping weekends and reviewed US market holidays). Same-day availability requires explicit source evidence or reviewed task input.
2. `equity_abnormal_activity_event` uses the explicit default `model_standard = equity_abnormal_activity_conservative` with `calibration_status = conservative_fixture_default_not_production_calibrated`. The default may produce conservative event evidence, but production training labels or promoted gates still require a reviewed historical calibration report.

## Historical-training readiness classification

There are no active data-stack design work items for the current no-broker historical-training preparation boundary. The non-data-accumulation policy layer is defined in `docs/40_production_hardening.md`, and the current manager/storage MVP owns request, manifest, artifact, ready-signal, payload, and receipt flow.

The following are deliberately not current historical-training work items:

- production packaging/service decisions beyond the implemented local source slices;
- broader production coverage source files beyond the accepted bounded start;
- optionability summary promotion before the model/control-plane contract needs it;
- optional ThetaData service/autostart setup before unattended option runs are accepted;
- production calibration reports for data-derived event standards before labels depend on them.

## Boundary acceptance

`trading-data` owns source acquisition, deterministic source-backed feature construction, point-in-time data visibility, and local development receipts. It does not own model promotion decisions, model labels/evaluation, broker execution, production scheduling/lifecycle retries, or final storage retention policy.

Production orchestration belongs to the manager/control-plane phase, with durable storage details coordinated through `trading-storage`.
