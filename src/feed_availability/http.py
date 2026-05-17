"""Small urllib transport for bounded probes."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from typing import Any, Callable


DEFAULT_TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 5_000_000
RETRYABLE_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded idempotent HTTP retry policy."""

    max_attempts: int = 1
    backoff_seconds: float = 0.0
    retry_statuses: frozenset[int] = RETRYABLE_HTTP_STATUSES
    respect_retry_after: bool = True
    max_retry_after_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")
        if self.max_retry_after_seconds < 0:
            raise ValueError("max_retry_after_seconds must be non-negative")

    def evidence(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "backoff_seconds": self.backoff_seconds,
            "retry_statuses": sorted(self.retry_statuses),
            "respect_retry_after": self.respect_retry_after,
            "max_retry_after_seconds": self.max_retry_after_seconds,
        }


@dataclass(frozen=True)
class HttpResult:
    url: str
    status: int | None
    headers: dict[str, str]
    body: bytes
    error_type: str | None = None
    error_message: str | None = None
    attempt_count: int = 1
    retry_after_seconds: float | None = None
    rate_limited: bool = False
    retry_policy: dict[str, Any] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class HttpClient:
    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        *,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResult:
        if params:
            separator = "&" if urllib.parse.urlparse(url).query else "?"
            url = url + separator + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers=headers or {}, method="GET")
        return self._open(request)

    def post_json(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> HttpResult:
        data = json.dumps(payload).encode("utf-8")
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        request = urllib.request.Request(
            url, data=data, headers=request_headers, method="POST"
        )
        return self._open(request)

    def _open(self, request: urllib.request.Request) -> HttpResult:
        attempts: list[dict[str, Any]] = []
        result: HttpResult | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            result = self._open_once(request)
            retry_after = _retry_after_seconds(result.headers)
            attempts.append(
                {
                    "attempt": attempt,
                    "status": result.status,
                    "error_type": result.error_type,
                    "retry_after_seconds": retry_after,
                    "retryable": self._is_retryable(result),
                }
            )
            if attempt >= self.retry_policy.max_attempts or not self._is_retryable(result):
                return replace(
                    result,
                    attempt_count=attempt,
                    attempts=attempts,
                    retry_after_seconds=retry_after,
                    rate_limited=result.status == 429,
                    retry_policy=self.retry_policy.evidence(),
                )
            delay = self._retry_delay(attempt=attempt, retry_after_seconds=retry_after)
            if delay > 0:
                self._sleep(delay)
        assert result is not None  # for type checkers; loop always returns
        return result

    def _open_once(self, request: urllib.request.Request) -> HttpResult:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return HttpResult(
                    url=request.full_url,
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(MAX_RESPONSE_BYTES),
                )
        except urllib.error.HTTPError as exc:
            return HttpResult(
                url=request.full_url,
                status=exc.code,
                headers=dict(exc.headers.items()) if exc.headers else {},
                body=exc.read(MAX_RESPONSE_BYTES),
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            return HttpResult(
                url=request.full_url,
                status=None,
                headers={},
                body=b"",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    def _is_retryable(self, result: HttpResult) -> bool:
        return result.status is None or result.status in self.retry_policy.retry_statuses

    def _retry_delay(self, *, attempt: int, retry_after_seconds: float | None) -> float:
        if self.retry_policy.respect_retry_after and retry_after_seconds is not None:
            return min(retry_after_seconds, self.retry_policy.max_retry_after_seconds)
        return self.retry_policy.backoff_seconds * (2 ** max(attempt - 1, 0))


def _retry_after_seconds(headers: dict[str, str]) -> float | None:
    for key, value in headers.items():
        if key.lower() == "retry-after":
            try:
                seconds = float(value)
            except (TypeError, ValueError):
                return None
            return max(seconds, 0.0)
    return None
