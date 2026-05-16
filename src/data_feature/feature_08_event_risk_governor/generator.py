"""Deterministic feature builder for Layer 8 EventRiskGovernor source rows."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

PRIORITY_RANK = {
    "official_disclosure": 1,
    "official_data_release": 1,
    "company_disclosure": 2,
    "regulatory_disclosure": 2,
    "source_detector": 3,
    "verified_news": 4,
    "broad_news": 5,
    "derivative_news": 6,
    "unknown": 9,
}

DERIVATIVE_DEDUP_STATUSES = {"covered_by_canonical_event", "duplicate_of_canonical_event"}


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _bool_int(value: bool) -> int:
    return 1 if value else 0


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    dedup_status = _text(row.get("dedup_status") or "canonical")
    source_priority = _text(row.get("source_priority") or "unknown")
    event_category = _text(row.get("event_category_type"))
    scope = _text(row.get("scope_type"))
    information_role = _text(row.get("information_role_type"))
    title = _text(row.get("title"))
    summary = _text(row.get("summary"))
    return {
        "event_category_type": event_category,
        "scope_type": scope,
        "information_role_type": information_role,
        "dedup_status": dedup_status,
        "source_priority": source_priority,
        "source_priority_rank": PRIORITY_RANK.get(source_priority, PRIORITY_RANK["unknown"]),
        "is_canonical_event": _bool_int(dedup_status == "canonical"),
        "is_derivative_or_duplicate_coverage": _bool_int(dedup_status in DERIVATIVE_DEDUP_STATUSES),
        "has_symbol_scope": _bool_int(bool(row.get("symbol"))),
        "has_sector_scope": _bool_int(bool(row.get("sector_type"))),
        "has_coverage_reason": _bool_int(bool(row.get("coverage_reason"))),
        "has_summary": _bool_int(bool(summary)),
        "title_length": len(title),
        "summary_length": len(summary),
        "reference_type": _text(row.get("reference_type")),
    }


def _quality(row: Mapping[str, Any]) -> dict[str, Any]:
    missing = [
        field
        for field in ("event_id", "canonical_event_id", "event_time", "available_time", "event_category_type", "scope_type", "source_name", "reference")
        if not row.get(field)
    ]
    return {
        "missing_required_fields": missing,
        "has_required_fields": not missing,
        "point_in_time_clock": "available_time",
        "source_table": "source_08_event_risk_governor",
    }


def generate_rows(rows: Iterable[Mapping[str, Any]], *, run_id: str = "feature_08_event_risk_governor") -> list[dict[str, Any]]:
    """Return deterministic event-risk evidence feature rows from source overview rows."""

    output: list[dict[str, Any]] = []
    for row in rows:
        event_id = row.get("event_id")
        available_time = row.get("available_time") or row.get("event_time")
        if not event_id or not available_time:
            continue
        output.append(
            {
                "run_id": run_id,
                "source_run_ref": row.get("source_run_ref") or row.get("run_id") or "source_08_event_risk_governor",
                "event_id": str(event_id),
                "canonical_event_id": str(row.get("canonical_event_id") or event_id),
                "event_time": row.get("event_time"),
                "available_time": available_time,
                "feature_payload_json": _payload(row),
                "feature_quality_diagnostics": _quality(row),
            }
        )
    return output
