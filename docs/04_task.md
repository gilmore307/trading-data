# Tasks

## Active Tasks

- Install and use the Temporal Explorer substrate as the shared calendar/timewheel foundation for dashboard and replay inspection. The first accepted slice creates the SQL tables, deterministic day spine, rule-generated venue sessions, and chart-cache contract without pretending that unconnected early-close, event-result, news-body, or chart-bar sources are populated.

The accepted local feed/source/feature route is structurally closed; see `docs/03_contracts.md`. Current data work should support historical evidence production for the first usable production-promotable model version, starting with Layer 1 `MarketRegimeModel` evidence/gate repair. Historical training may proceed through manager-planned request payloads, handoff validation, and autonomous historical provider acquisition under bounded manager controls. Realtime feed/source expansion is parked until a model has an approved/promotable version.

## Historical-Training Readiness Status

- Current route coverage is accepted for the bounded historical training start: Alpaca bars/liquidity/news, GDELT news, OKX public market data, Trading Economics storage-snapshot calendar rows, SEC company financials, ThetaData option primary tracking, and ThetaData option event timeline.
- Source-specific dry-run parameter defaults are manager-owned in `trading-manager/src/trading_manager_tasks/request_payloads.py`; `trading-data` should not duplicate that control-plane policy locally.
- Manager/storage V1 request, manifest, artifact, and ready-signal contracts are accepted and implemented through the current manager/storage MVP path; `trading-data` consumes task-key payloads and emits component evidence, not manager lifecycle state.
- Event standards remain conservative evidence until reviewed historical calibration reports promote them into labels/gates.
- Candidate-dependent Alpaca target-state rows remain deferred until manager-issued candidate rows or reviewed local bar/liquidity artifacts are supplied.

## Not Current Historical-Training Scope

These items are intentionally outside the current promote-first historical-training run and must not be treated as open repository work items:

- realtime feed/source expansion before a model has an approved/promotable version;
- broader production packaging/service management beyond local source slices;
- unattended ThetaData service/autostart setup;
- optionability-summary promotion before a model/control-plane consumer requires it;
- broader historical ETF issuer archives before point-in-time availability is reviewed;
- production data-derived event label/gate calibration before reviewed historical reports exist.

## Current Accepted Details

- Alpaca bars treats provider `bars: null` no-data responses as empty successful acquisitions with headers/schema/manifests rather than failed component receipts. This supports historical months where current-universe symbols did not yet have bars.
- Repository data-stack acceptance: current feed/source/feature surfaces cover the accepted local Layers 1-9 model-input route.
- Production hardening policy: provider-call guardrails, retry/rate-limit rules, checkpoint/resume evidence, manifests, artifact refs, and ready signals are documented in `docs/40_production_hardening.md`.
- Storage-owned V1 handoff contracts are the production handoff vocabulary; file artifacts and runtime evidence belong under `trading-storage/storage/01_source_data/`.
- ThetaData Terminal is installed outside Git and a controlled live smoke succeeded through `10_feed_thetadata_option_primary_tracking`.
- `m02_sector_context_data_acquisition` is retired from the current ordinary candidate route. ETF holdings may remain standalone source evidence, but they do not define the realtime total pool, Layer 2 feature generation, or historical replay candidates.
- `equity_abnormal_activity_event` uses `equity_abnormal_activity_conservative` with `conservative_fixture_default_not_production_calibrated` until reviewed calibration exists.
- `price_action` is accepted as a Layer 10 event-risk category for false breakout / failed breakdown / liquidity sweep / bull-trap / bear-trap evidence; it remains event-risk evidence, not a new model layer or trading action.
- `m03_target_state_vector_data_acquisition` and `m03_target_state_vector_feature_generation` implement deterministic target-local observed-input and feature-block surfaces.
- Layer 2 / candidate / Layer 3 boundaries are aligned: Layer 2 emits sector/context features only; Layer 3 consumes target-local candidate evidence and accepted target-context mappings without relying on ETF holdings acquisition.
- Event overlay sources are accepted through `m10_event_risk_governor_data_acquisition`, including equity abnormal activity evidence.
- Option-expression inputs are accepted through shared `option_chain_state_source` plus `m09_option_expression_feature_generation`; selected-contract tracking remains `m09_option_expression_data_acquisition_contract_path`.
- Final non-TE feed outputs are SQL rows plus concise receipts/schema evidence; no JSONL/CSV mirror is written by default. Trading Economics calendar source rows remain the protected source-data exception.
- Alpaca bars, liquidity, and news feeds are implemented with bounded pagination, ET timestamp normalization, completion receipts, and no default bulky raw persistence.
- ThetaData option feeds are implemented for selection snapshot, specified-contract primary tracking, and event timeline.
- `feed_availability` and `feed_interfaces` provide bounded provider/data-kind inventory and smoke support.
- `macro_data` is not active. Macro source evidence is canonical Trading Economics storage data; shared calendar maintenance may append recent/future TE calendar source rows and Nasdaq earnings schedule artifacts but must not persist TE website URLs or populate Layer 10 SQL rows.
- Current task key / receipt fields are registered through `trading-manager`; new shared fields need registry review.

## Closed Design Notes

Broad domain labels — market board, instrument, option — are product concepts only. The repository follows the direct route:

```text
data_feed -> data_source -> data_feature -> SQL/artifact handoff
```

New work should extend that route rather than adding parallel ad hoc scripts or new historical naming layers.
