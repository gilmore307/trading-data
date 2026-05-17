# Tasks

## Active Tasks

- None for the repository-design boundary in the current promote-first model phase.

The accepted local feed/source/feature route is structurally closed; see `docs/03_contracts.md`. Current data work should support historical evidence production for the first usable production-promotable model version, starting with Layer 1 `MarketRegimeModel` evidence/gate repair. Historical training may proceed through manager-planned request payloads, handoff validation, and autonomous historical provider acquisition under bounded manager controls. Realtime feed/source expansion is parked until a model has an approved/promotable version.

## Historical-Training Readiness Status

- Current route coverage is accepted for the bounded historical training start: Alpaca bars/liquidity/news, GDELT news, SEC company financials, ThetaData option primary tracking, and ThetaData option event timeline.
- Source-specific dry-run parameter defaults are now manager-owned in `trading-manager/src/trading_manager_tasks/request_payloads.py`; `trading-data` should not duplicate that control-plane policy locally.
- Manager/storage V1 request, manifest, artifact, and ready-signal contracts are accepted and implemented through the current manager/storage MVP path; `trading-data` consumes task-key payloads and emits component evidence, not manager lifecycle state.
- Event standards remain conservative evidence until reviewed historical calibration reports promote them into labels/gates.

## Not Current Historical-Training Scope

These items are intentionally outside the current promote-first historical-training run and must not be treated as open repository work items:

- realtime feed/source expansion before a model has an approved/promotable version;
- broader production packaging/service management beyond local source slices;
- unattended ThetaData service/autostart setup;
- optionability-summary promotion before a model/control-plane consumer requires it;
- broader ETF issuer adapters before historical point-in-time source archives are reviewed;
- production data-derived event label/gate calibration before reviewed historical reports exist.

## Recently Accepted

- Alpaca bars now treats provider `bars: null` no-data responses as empty successful acquisitions with headers/schema/manifests rather than failed component receipts. This supports historical months where current-universe symbols did not yet have bars.
- Repository data-stack acceptance: current feed/source/feature surfaces cover the accepted local Layers 1-8 model-input route.
- Production hardening policy: provider-call guardrails, retry/rate-limit rules, checkpoint/resume evidence, manifests, artifact refs, and ready signals are documented in `docs/40_production_hardening.md`.
- Storage-owned V1 handoff contracts are the production handoff vocabulary; local ignored `storage/` remains development evidence.
- ThetaData Terminal is installed outside Git and a controlled live smoke succeeded through `10_feed_thetadata_option_primary_tracking`.
- `source_02_target_candidate_holdings` preserves point-in-time visibility with a conservative next-session-open default when no explicit availability timestamp exists.
- `equity_abnormal_activity_event` uses `equity_abnormal_activity_conservative` with `conservative_fixture_default_not_production_calibrated` until reviewed calibration exists.
- `price_action` is accepted as a Layer 9 event-risk category for false breakout / failed breakdown / liquidity sweep / bull-trap / bear-trap evidence; it remains event-risk evidence, not a new model layer or trading action.
- `source_03_target_state` and `feature_03_target_state_vector` implement deterministic target-local observed-input and feature-block surfaces.
- Layer 2 / candidate / Layer 3 boundaries are aligned: ETF holdings and `stock_etf_exposure` support anonymous target candidate preparation, not Layer 2 core behavior.
- Event overlay sources are accepted through `source_09_event_risk_governor`, including equity abnormal activity evidence.
- Option-expression inputs are accepted through `source_05_option_expression` and selected-contract tracking through `source_06_position_execution`.
- Final saved source outputs are CSV or explicitly reviewed compact artifacts; JSONL may exist only as transient run-local evidence.
- Alpaca bars, liquidity, and news feeds are implemented with bounded pagination, ET timestamp normalization, completion receipts, and no default bulky raw persistence.
- ThetaData option feeds are implemented for selection snapshot, specified-contract primary tracking, and event timeline.
- `feed_availability` and `feed_interfaces` provide bounded provider/data-kind inventory and smoke support.
- `macro_data` is not active. Macro model-input rows use `07_feed_trading_economics_calendar_web` visible-page evidence.
- Current task key / receipt fields are registered through `trading-manager`; new shared fields need registry review.

## Closed Design Notes

Broad domain labels — market board, instrument, option — are product concepts only. The repository follows the direct route:

```text
data_feed -> data_source -> data_feature -> SQL/artifact handoff
```

New work should extend that route rather than adding parallel ad hoc scripts or new historical naming layers.
