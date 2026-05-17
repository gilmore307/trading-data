# Production Hardening

This document records the production-hardening contracts that can be defined before accumulated production labels/data exist. It does not approve unattended production orchestration.

## Boundary

`trading-data` owns provider/source acquisition and normalized source/feature outputs. `trading-manager` owns requests, scheduling, approvals, and control-plane policy. `trading-storage` owns durable manifests, artifact references, ready signals, retention, backup, and restore.

Local ignored `storage/` outputs remain development evidence. Production handoff must use the storage-owned V1 contracts:

- `manager_request`
- `run_manifest`
- `artifact_ref`
- `ready_signal`

## Provider-Call Guardrails

Historical provider/API acquisition may run autonomously when issued by `trading-manager` under bounded manager controls. The retired manual approval-packet path is not part of the active historical route.

Required manager-control fields for autonomous historical acquisition:

- `allow_live_provider_calls`
- `autonomous_historical_provider_acquisition`
- `allowed_providers`
- `allowed_endpoint_families`
- `max_requests`
- `max_rows` or `max_symbols` where meaningful
- `max_time_window`
- `timeout_seconds`
- `retry_policy_ref`
- `rate_limit_policy_ref`
- `secret_alias_refs`

Enforcement helper: `src/data_runtime/provider_policy.py` provides `require_provider_execution_allowed(...)`. Live provider clients must call it before loading provider secrets, constructing real clients, or issuing network/API requests. Fixture/fake-client and local-file/text modes remain exempt because they do not perform live provider calls.

Rules:

- Secret values must never be logged, persisted, committed, or embedded in manifests.
- Provider errors, HTTP statuses, rate-limit responses, and retry counts belong in sanitized manifest evidence.
- `Retry-After` or provider-specific backoff headers must be respected.
- Missing or unsupported manager controls must fail closed.
- Broker execution, account/order mutation, storage lifecycle mutation, and production model activation remain separate hard-gated surfaces.

## Retry / Rate-Limit Policy

Minimum retry policy:

- retry only idempotent fetch segments;
- record attempt count per segment;
- use bounded exponential backoff or provider-mandated wait;
- stop at `max_attempts`;
- classify terminal failures as retry-exhausted, entitlement-blocked, invalid-request, provider-unavailable, or policy-blocked.

Retries must not duplicate ready outputs. A retried segment can replace only its own incomplete segment state before final manifest validation.

## Checkpoint / Resume Evidence

Segmented runs must write checkpoint evidence into the run manifest or a referenced checkpoint artifact.

Required segment evidence:

- `segment_id`
- `segment_order`
- `provider`
- `endpoint_family`
- `parameter_fingerprint`
- `source_time_window`
- `segment_status`: `pending`, `running`, `succeeded`, `failed`, `skipped`, or `superseded`
- `last_successful_cursor` or explicit no-cursor marker
- `attempt_count`
- `row_count`
- `started_at`
- `finished_at`
- `error_class` / `error_message` when failed

Resume rules:

- resume by segment id and parameter fingerprint, not by mutable local filenames;
- succeeded immutable segments must not be re-fetched unless a new request supersedes the original;
- partial or failed segments must not emit `ready_signal` with `ready_status = ready`;
- partial coverage may emit `partial_ready` only when the downstream request explicitly permits partial input coverage.

## Manifest / Ready Signal Rules

Every production candidate run must emit or persist:

1. `run_manifest` with request, git commit, config refs, provider evidence, validation checks, input refs, and output refs.
2. `artifact_ref` for every durable output artifact.
3. `ready_signal` only after required validation checks pass.

Consumers must reject artifacts without a compatible ready signal.

## ThetaData Runbook

ThetaData remains the registered options-data provider for option snapshot, OHLC, trade/quote, Greeks, and related endpoint families.

Local runtime expectation:

- JAR/runtime path: `/root/tools/thetadata-terminal/ThetaTerminalv3.jar`
- Default terminal endpoint: `http://127.0.0.1:25503`
- Secret alias: `thetadata`; secret material remains under `/root/secrets/` and must not be printed or committed.

Controlled smoke checklist:

1. Confirm the local terminal port is reachable.
2. Run a small, explicitly bounded endpoint request through an existing ThetaData feed CLI.
3. Limit to one underlying/contract and a short reviewed time window.
4. Record sanitized endpoint family, status, row count, entitlement status, and elapsed time in the manifest evidence.
5. Do not persist raw provider responses by default.

Current local check: ThetaData Terminal is installed at `/root/tools/thetadata-terminal/ThetaTerminalv3.jar` and can be started locally with the checked-in runtime config plus secret material kept outside Git. On 2026-05-08, a controlled live smoke succeeded against `127.0.0.1:25503` using `10_feed_thetadata_option_primary_tracking` for AAPL 2026-05-15 270 CALL on 2026-04-24 at `1Min`: 443 active transient OHLC rows aggregated into 242 saved `option_bar` rows under `/tmp/thetadata-live-smoke-20260508044010/`. If the port is closed, the task is runtime-not-started rather than connector-not-integrated.

## Realtime validation handoff

Realtime or live-observed source rows can support model forward-validation only after the manager/model stack treats them as append-only point-in-time evidence. Required handoff facts include observation time, provider available time, tradeable time, frozen model/config refs, prediction/output refs, label maturity time, and outcome label refs.

The handoff must remain separate from historical provider backfill: realtime capture can become `forward_holdout` or `shadow_monitoring` evidence, but it must not silently rewrite historical train/calibration/validation/test snapshots and must not be used for refit before a reviewed dataset snapshot boundary.

## Non-Production Status

These policies make production entry stricter; they do not create production labels, approve model promotion, or authorize unattended live orchestration.
