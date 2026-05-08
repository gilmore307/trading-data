# Production Hardening

This document records the production-hardening contracts that can be defined before accumulated production labels/data exist. It does not approve unattended production orchestration.

## Boundary

`trading-data` owns provider/source acquisition and normalized source/feature outputs. `trading-manager` owns requests, scheduling, approvals, and control-plane policy. `trading-storage` owns durable manifests, artifact references, ready signals, retention, backup, and restore.

Local ignored `storage/` outputs remain development evidence. Production handoff must use the storage-owned V1 contracts:

- `manager_request_v1`
- `run_manifest_v1`
- `artifact_ref_v1`
- `ready_signal_v1`

## Live-Call Guardrails

Live provider/API calls are disabled by default for manager-issued requests unless the request includes an explicit `live_call_policy`.

Required live-call policy fields:

- `allow_live_calls`
- `allowed_providers`
- `allowed_endpoint_families`
- `max_requests`
- `max_rows` or `max_symbols` where meaningful
- `max_time_window`
- `timeout_seconds`
- `retry_policy_ref`
- `rate_limit_policy_ref`
- `secret_alias_refs`
- `manual_approval_ref` for `production` mode

Rules:

- Secret values must never be logged, persisted, committed, or embedded in manifests.
- Provider errors, HTTP statuses, rate-limit responses, and retry counts belong in sanitized manifest evidence.
- `Retry-After` or provider-specific backoff headers must be respected.
- Any missing/unsupported live-call policy must fail closed.

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
- partial or failed segments must not emit `ready_signal_v1` with `ready_status = ready`;
- partial coverage may emit `partial_ready` only when the downstream request explicitly permits partial input coverage.

## Manifest / Ready Signal Rules

Every production candidate run must emit or persist:

1. `run_manifest_v1` with request, git commit, config refs, provider evidence, validation checks, input refs, and output refs.
2. `artifact_ref_v1` for every durable output artifact.
3. `ready_signal_v1` only after required validation checks pass.

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

Current local check: the ThetaData terminal port must be open before a controlled live smoke can run. If the port is closed, the task is environment-blocked rather than production-data-blocked.

## Non-Production Status

These policies make the future production path stricter; they do not create production labels, approve model promotion, or authorize unattended live orchestration.
