# Task

## Active Tasks

- None for the accepted local feed/source/feature route. The current data route is structurally closed; see `docs/95_data_stack_closeout.md`.

## Production-Hardening Queue

These are ready-now hardening items, separate from accumulated production-data/model-label evidence:

- Implement physical manager/storage queue and SQL/storage handling for `manager_request_v1`, `run_manifest_v1`, `artifact_ref_v1`, and `ready_signal_v1`.
- Define source-specific production parameter dictionaries for registered `data_kind` rows.
- Expand ETF issuer adapters after the issuer priority list and source-file formats are reviewed.
- Promote an optionability summary interface only when the model/control-plane contract needs it.
- Produce reviewed historical calibration reports before any data-derived event standard becomes a production label or gate.
- Configure ThetaData runtime as an intentional service/autostart item if unattended option data runs become accepted.

## Recently Accepted

- Repository data-stack closeout: current feed/source/feature surfaces cover the accepted local Layers 1-8 model-input route.
- Production hardening policy: live-call guardrails, retry/rate-limit rules, checkpoint/resume evidence, manifests, artifact refs, and ready signals are documented in `docs/96_production_hardening.md`.
- Storage-owned V1 handoff contracts are the production handoff vocabulary; local ignored `storage/` remains development evidence.
- ThetaData Terminal is installed outside Git and a controlled live smoke succeeded through `10_feed_thetadata_option_primary_tracking`.
- `source_02_target_candidate_holdings` preserves point-in-time visibility with a conservative next-session-open default when no explicit availability timestamp exists.
- `equity_abnormal_activity_event` uses `equity_abnormal_activity_conservative_v1` with `conservative_fixture_default_not_production_calibrated` until reviewed calibration exists.
- `price_action` is accepted as a Layer 4 event category for false breakout / failed breakdown / liquidity sweep / bull-trap / bear-trap evidence; it remains event-overlay evidence, not a new model layer or trading action.
- `source_03_target_state` and `feature_03_target_state_vector` implement deterministic target-local observed-input and feature-block surfaces.
- Layer 2 / candidate / Layer 3 boundaries are aligned: ETF holdings and `stock_etf_exposure` support anonymous target candidate preparation, not Layer 2 core behavior.
- Event overlay sources are accepted through `source_04_event_overlay`, including equity abnormal activity evidence.
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
