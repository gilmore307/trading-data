"""Fail-closed provider execution policy for live acquisition paths.

Fixture/local runs pass fake clients or local payload paths and do not need live
provider authorization. Real provider clients must be backed by manager-issued
controls in the task key before credentials or network calls are used.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping, Sequence


class ProviderPolicyError(ValueError):
    """Raised when a task key does not authorize live provider execution."""


@dataclass(frozen=True)
class ProviderPolicy:
    """Accepted live-provider execution envelope."""

    contract_type: str
    provider: str
    endpoint_family: str
    max_requests: int | None
    max_rows: int | None
    max_symbols: int | None
    max_time_window: str | None
    timeout_seconds: int | None
    retry_policy_ref: str | None
    rate_limit_policy_ref: str | None

    def summary_row(self) -> dict[str, Any]:
        return asdict(self)


def _controls(task_key: Mapping[str, Any]) -> Mapping[str, Any]:
    controls = task_key.get("manager_controls") or {}
    if not isinstance(controls, Mapping):
        raise ProviderPolicyError("manager_controls must be an object")
    return controls


def _allowed(value: str, allowed_values: object, *, field_name: str) -> bool:
    if allowed_values is None:
        return False
    if isinstance(allowed_values, str):
        allowed = [allowed_values]
    elif isinstance(allowed_values, Sequence):
        allowed = [str(item) for item in allowed_values]
    else:
        raise ProviderPolicyError(f"manager_controls.{field_name} must be a list or '*' string")
    return "*" in allowed or value in allowed


def _optional_int(controls: Mapping[str, Any], key: str) -> int | None:
    value = controls.get(key)
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ProviderPolicyError(f"manager_controls.{key} must be an integer") from exc
    if parsed < 0:
        raise ProviderPolicyError(f"manager_controls.{key} must be non-negative")
    return parsed


def _check_limit(*, name: str, requested: int | None, allowed: int | None) -> None:
    if requested is None or allowed is None:
        return
    if requested > allowed:
        raise ProviderPolicyError(f"requested {name} exceeds manager_controls.max_{name}: {requested} > {allowed}")


def _parse_datetime(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ProviderPolicyError("requested time window bounds must be non-empty strings")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ProviderPolicyError(f"requested time window bound is not ISO-like: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_time_window(value: object) -> timedelta | None:
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    iso_match = re.fullmatch(r"p(?:(\d+)m)?(?:(\d+)d)?", text)
    if iso_match:
        months = int(iso_match.group(1) or 0)
        days = int(iso_match.group(2) or 0)
        if months == 0 and days == 0:
            raise ProviderPolicyError("manager_controls.max_time_window must be positive")
        return timedelta(days=months * 31 + days)
    simple_match = re.fullmatch(r"(\d+)(d|day|days|mo|month|months)", text)
    if simple_match:
        amount = int(simple_match.group(1))
        if amount <= 0:
            raise ProviderPolicyError("manager_controls.max_time_window must be positive")
        unit = simple_match.group(2)
        return timedelta(days=amount * 31 if unit.startswith("mo") else amount)
    raise ProviderPolicyError("manager_controls.max_time_window must use a supported duration such as 1d, 31d, 6mo, or P31D")


def _check_time_window(*, requested_start: str | None, requested_end: str | None, allowed_text: object) -> None:
    allowed = _parse_time_window(allowed_text)
    if allowed is None or requested_start in (None, "") or requested_end in (None, ""):
        return
    start = _parse_datetime(str(requested_start))
    end = _parse_datetime(str(requested_end))
    if end < start:
        raise ProviderPolicyError("requested time window end is before start")
    requested = end - start
    if requested > allowed:
        raise ProviderPolicyError(f"requested time window exceeds manager_controls.max_time_window: {requested} > {allowed}")


def require_provider_execution_allowed(
    task_key: Mapping[str, Any],
    *,
    provider: str,
    endpoint_family: str,
    requested_symbols: int | None = None,
    requested_rows: int | None = None,
    requested_requests: int | None = None,
    requested_start: str | None = None,
    requested_end: str | None = None,
) -> ProviderPolicy:
    """Validate that a manager task key permits live provider execution.

    This function intentionally fails closed. Callers should invoke it before
    constructing a real provider client, loading provider secrets, or issuing
    network/API requests. Tests and fixture paths should pass fake/local clients
    and skip live-provider execution entirely.
    """

    provider = str(provider or "").strip()
    endpoint_family = str(endpoint_family or "").strip()
    if not provider:
        raise ProviderPolicyError("provider is required")
    if not endpoint_family:
        raise ProviderPolicyError("endpoint_family is required")
    controls = _controls(task_key)
    if controls.get("allow_live_provider_calls") is not True:
        raise ProviderPolicyError("live provider calls are not allowed")
    if controls.get("autonomous_historical_provider_acquisition") is not True:
        raise ProviderPolicyError("autonomous historical acquisition is not allowed")
    if not _allowed(provider, controls.get("allowed_providers"), field_name="allowed_providers"):
        raise ProviderPolicyError(f"provider not allowed: {provider}")
    if not _allowed(endpoint_family, controls.get("allowed_endpoint_families"), field_name="allowed_endpoint_families"):
        raise ProviderPolicyError(f"endpoint family not allowed: {endpoint_family}")

    max_requests = _optional_int(controls, "max_requests")
    max_rows = _optional_int(controls, "max_rows")
    max_symbols = _optional_int(controls, "max_symbols")
    max_time_window = str(controls.get("max_time_window") or "") or None
    timeout_seconds = _optional_int(controls, "timeout_seconds")
    _check_limit(name="requests", requested=requested_requests, allowed=max_requests)
    _check_limit(name="rows", requested=requested_rows, allowed=max_rows)
    _check_limit(name="symbols", requested=requested_symbols, allowed=max_symbols)
    _check_time_window(requested_start=requested_start, requested_end=requested_end, allowed_text=max_time_window)
    return ProviderPolicy(
        contract_type="provider_execution_policy",
        provider=provider,
        endpoint_family=endpoint_family,
        max_requests=max_requests,
        max_rows=max_rows,
        max_symbols=max_symbols,
        max_time_window=max_time_window,
        timeout_seconds=timeout_seconds,
        retry_policy_ref=str(controls.get("retry_policy_ref") or "") or None,
        rate_limit_policy_ref=str(controls.get("rate_limit_policy_ref") or "") or None,
    )


__all__ = ["ProviderPolicy", "ProviderPolicyError", "require_provider_execution_allowed"]
