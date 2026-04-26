"""Small urllib transport for bounded probes."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 192_000


@dataclass(frozen=True)
class HttpResult:
    url: str
    status: int | None
    headers: dict[str, str]
    body: bytes
    error_type: str | None = None
    error_message: str | None = None

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class HttpClient:
    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds

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
