"""Sanitize provider responses before writing reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_TOKENS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "passphrase",
    "password",
    "registrationkey",
    "secret",
    "secret_key",
    "token",
    "user_id",
    "userid",
)


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(token in lowered for token in SENSITIVE_TOKENS)


def sanitize_value(value: Any, max_string: int = 180) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[redacted]" if is_sensitive_key(str(key)) else sanitize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [sanitize_value(item) for item in list(value)[:5]]
    if isinstance(value, str):
        if len(value) > max_string:
            return value[:max_string] + "...[truncated]"
        return value
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)[:max_string]


def shape_keys(payload: Any) -> list[str]:
    if isinstance(payload, Mapping):
        return sorted(str(key) for key in payload.keys())[:30]
    if isinstance(payload, Sequence) and not isinstance(payload, str):
        if not payload:
            return []
        first = payload[0]
        if isinstance(first, Mapping):
            return sorted(str(key) for key in first.keys())[:30]
        if isinstance(first, Sequence) and not isinstance(first, str):
            return [f"column_{index}" for index, _ in enumerate(first[:30])]
    return []


def sample_rows(payload: Any, row_path: tuple[str, ...] = (), limit: int = 2) -> list[Any]:
    target = payload
    for key in row_path:
        if isinstance(target, Mapping):
            target = target.get(key)
        else:
            target = None
            break
    if isinstance(target, list):
        return [sanitize_value(row) for row in target[:limit]]
    if isinstance(target, Mapping):
        return [sanitize_value(target)]
    return []


def sanitize_url(url: str | None) -> str | None:
    if url is None:
        return None
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        sensitive = key.lower() == "key" or is_sensitive_key(key)
        query.append((key, "[redacted]" if sensitive else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
