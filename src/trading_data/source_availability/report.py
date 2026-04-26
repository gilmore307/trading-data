"""Report model and writer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import SourceCandidate


DEFAULT_REPORT_ROOT = Path("data/storage/source_availability")


@dataclass
class ProbeResult:
    source: str
    status: str
    available: bool
    data_kind_candidates: list[str]
    access: str
    docs_url: str
    endpoint: str | None = None
    http_status: int | None = None
    response_shape_keys: list[str] = field(default_factory=list)
    sample_rows: list[Any] = field(default_factory=list)
    secret_alias: dict[str, Any] | None = None
    skipped_reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def skipped(
        cls,
        candidate: SourceCandidate,
        reason: str,
        *,
        secret_alias: dict[str, Any] | None = None,
    ) -> "ProbeResult":
        return cls(
            source=candidate.source,
            status="skipped",
            available=False,
            data_kind_candidates=list(candidate.data_kind_candidates),
            access=candidate.access,
            docs_url=candidate.docs_url,
            secret_alias=secret_alias,
            skipped_reason=reason,
        )


def report_payload(results: list[ProbeResult], *, mode: str) -> dict[str, Any]:
    return {
        "report_type": "source_availability",
        "mode": mode,
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "results": [asdict(result) for result in results],
    }


def write_report(
    results: list[ProbeResult],
    *,
    mode: str,
    report_root: Path = DEFAULT_REPORT_ROOT,
) -> Path:
    report_root.mkdir(parents=True, exist_ok=True)
    timestamp = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "")
    )
    path = report_root / f"source_availability_{timestamp}.json"
    path.write_text(
        json.dumps(report_payload(results, mode=mode), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
