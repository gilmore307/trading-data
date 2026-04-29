"""Manager-facing 07 EventOverlayModel event overview bundle."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from trading_data.source_availability.sanitize import sanitize_value
from trading_data.storage.sql import PostgresSqlTableWriter, SqlTableWriter

BUNDLE = "07_bundle_event_overlay"
MODEL_ID = "event_overlay_model"
OUTPUT_TABLE = "event_overlay_event"
ET = ZoneInfo("America/New_York")
INFORMATION_ROLES = {"lagging_evidence", "prior_signal"}
EVENT_CATEGORIES = {"macro_data", "macro_news", "sector_news", "symbol_news", "sec_filing", "option_abnormal_activity", "equity_abnormal_activity"}
SCOPE_TYPES = {"macro", "sector", "symbol"}
REFERENCE_TYPES = {"web_url", "sec_file_path", "internal_artifact_path", "source_reference"}
SQL_FIELDS = [
    "event_id",
    "event_time",
    "available_time",
    "information_role_type",
    "event_category_type",
    "scope_type",
    "symbol",
    "sector_type",
    "title",
    "summary",
    "source_name",
    "reference_type",
    "reference",
]
KEY_COLUMNS = ["event_id"]


@dataclass(frozen=True)
class BundleContext:
    task_key: dict[str, Any]
    run_dir: Path
    receipt_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepResult:
    status: str
    references: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourcePayload:
    start: str
    end: str
    focus_sectors: list[str]
    symbols: list[str]
    events: list[dict[str, Any]]


@dataclass(frozen=True)
class CleanedPayload:
    rows: list[dict[str, Any]]


class EventOverlayInputsError(ValueError):
    """Raised for invalid EventOverlayModel input tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise EventOverlayInputsError(f"params.{key} is required")
    return value


def _as_list(value: Any) -> list[Any]:
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return value
    return [value]


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _et_iso(value: Any) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventOverlayInputsError(f"invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET).isoformat()


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise EventOverlayInputsError(f"task_key.bundle must be {BUNDLE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    return BundleContext(task_key, output_root / "runs" / run_id, output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def fetch(context: BundleContext) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    start = str(_required(params, "start"))
    end = str(_required(params, "end"))
    focus_sectors = _string_list(params.get("focus_sectors") or params.get("sectors"))
    symbols = [item.upper() for item in _string_list(params.get("symbols"))]
    events = [dict(item) for item in _as_list(_required(params, "events")) if isinstance(item, Mapping)]
    if not events:
        raise EventOverlayInputsError("params.events must contain at least one event overview row")
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(json.dumps(sanitize_value({"bundle": BUNDLE, "model_id": MODEL_ID, "start": start, "end": end, "focus_sectors": focus_sectors, "symbols": symbols, "event_count": len(events), "raw_persistence": "event details remain behind references; SQL stores overview rows only", "fetched_at_utc": _now_utc()}), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest)], {"raw_event_overview_rows": len(events)}, details={"event_count": len(events)}), SourcePayload(start, end, focus_sectors, symbols, events)


def _enum(value: Any, allowed: set[str], field_name: str) -> str:
    text = str(value or "").strip().lower()
    if text not in allowed:
        raise EventOverlayInputsError(f"{field_name} must be one of {sorted(allowed)}")
    return text


def _event_id(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("event_id") or "").strip()
    if explicit:
        return explicit
    category = str(row.get("event_category_type") or "event").strip().lower()
    event_time = str(row.get("event_time") or row.get("available_time") or "").strip()
    reference = str(row.get("reference") or row.get("event_link_url") or row.get("source_reference") or "").strip()
    symbol = str(row.get("symbol") or "").strip().upper()
    base = "|".join([category, event_time, symbol, reference])
    return "evt_" + str(abs(hash(base)))


def clean(context: BundleContext, payload: SourcePayload) -> tuple[StepResult, CleanedPayload]:
    rows: list[dict[str, Any]] = []
    for source in payload.events:
        reference = str(source.get("reference") or source.get("event_link_url") or source.get("source_reference") or source.get("sec_file_path") or "").strip()
        if not reference:
            raise EventOverlayInputsError("each event requires reference/link/path")
        row = {
            "event_id": _event_id(source),
            "event_time": _et_iso(_required(source, "event_time")),
            "available_time": _et_iso(source.get("available_time") or source.get("event_time")),
            "information_role_type": _enum(source.get("information_role_type"), INFORMATION_ROLES, "information_role_type"),
            "event_category_type": _enum(source.get("event_category_type"), EVENT_CATEGORIES, "event_category_type"),
            "scope_type": _enum(source.get("scope_type"), SCOPE_TYPES, "scope_type"),
            "symbol": str(source.get("symbol") or "").strip().upper() or None,
            "sector_type": str(source.get("sector_type") or "").strip() or None,
            "title": str(source.get("title") or source.get("headline") or "").strip(),
            "summary": str(source.get("summary") or "").strip(),
            "source_name": str(source.get("source_name") or source.get("source") or "").strip(),
            "reference_type": _enum(source.get("reference_type") or "source_reference", REFERENCE_TYPES, "reference_type"),
            "reference": reference,
        }
        if not row["title"]:
            raise EventOverlayInputsError("each event requires title/headline")
        rows.append(row)
    rows.sort(key=lambda item: (item["event_time"], item["event_id"]))
    return StepResult("succeeded", [], {OUTPUT_TABLE: len(rows)}, details={"table": OUTPUT_TABLE, "columns": SQL_FIELDS, "natural_key": KEY_COLUMNS}), CleanedPayload(rows)


def save(context: BundleContext, clean_result: StepResult, payload: CleanedPayload, *, sql_writer: SqlTableWriter | None = None) -> StepResult:
    writer = sql_writer or PostgresSqlTableWriter.from_config({})
    metadata = writer.write_rows(table=OUTPUT_TABLE, columns=SQL_FIELDS, rows=payload.rows, key_columns=KEY_COLUMNS)
    reference = str(metadata.get("qualified_table") or metadata.get("table") or OUTPUT_TABLE)
    return StepResult("succeeded", [reference], dict(clean_result.row_counts), details={"format": "sql_table", "table": OUTPUT_TABLE, "columns": SQL_FIELDS, "storage": metadata})


def write_receipt(context: BundleContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: BaseException | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "bundle": BUNDLE, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": str(context.metadata["run_id"]), "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != entry["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "bundle": BUNDLE})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": entry["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str, sql_writer: SqlTableWriter | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, source_payload = fetch(context)
        clean_result, cleaned_payload = clean(context, source_payload)
        save_result = save(context, clean_result, cleaned_payload, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
