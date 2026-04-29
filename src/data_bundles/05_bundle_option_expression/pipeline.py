"""Manager-facing 05 OptionExpressionModel option snapshot input bundle."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from data_sources.thetadata_option_selection_snapshot.pipeline import build_context as build_snapshot_context
from data_sources.thetadata_option_selection_snapshot.pipeline import clean as clean_snapshot
from data_sources.thetadata_option_selection_snapshot.pipeline import fetch as fetch_snapshot
from source_availability.http import HttpClient
from source_availability.sanitize import sanitize_value
from storage.sql import PostgresSqlTableWriter, SqlTableWriter

BUNDLE = "05_bundle_option_expression"
MODEL_ID = "option_expression_model"
OUTPUT_TABLE = "bundle_05_option_expression"
SQL_FIELDS = ["run_id", "task_id", "underlying", "snapshot_time", "contract_count", "contracts"]
KEY_COLUMNS = ["run_id", "underlying", "snapshot_time"]


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
    snapshot: dict[str, Any]
    contract_count: int
    fetch_result: Any
    clean_result: Any


@dataclass(frozen=True)
class CleanedPayload:
    rows: list[dict[str, Any]]


class OptionExpressionInputsError(ValueError):
    """Raised for invalid OptionExpressionModel input tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise OptionExpressionInputsError(f"task_key.bundle must be {BUNDLE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    return BundleContext(task_key, output_root / "runs" / run_id, output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def fetch(context: BundleContext, *, client: HttpClient | None = None) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    source_task = {
        "task_id": f"{context.task_key.get('task_id')}_option_snapshot",
        "bundle": "thetadata_option_selection_snapshot",
        "params": params,
        "output_root": str(context.run_dir / "source" / "option_chain_snapshot"),
    }
    source_context = build_snapshot_context(source_task, str(context.metadata["run_id"]))
    fetch_result, fetched = fetch_snapshot(source_context, client=client)
    clean_result, snapshot = clean_snapshot(source_context, fetched)
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(json.dumps(sanitize_value({"bundle": BUNDLE, "model_id": MODEL_ID, "source_bundle": "thetadata_option_selection_snapshot", "params": {"underlying": params.get("underlying"), "snapshot_time": params.get("snapshot_time")}, "source_fetch": asdict(fetch_result), "source_clean": asdict(clean_result), "raw_persistence": "ThetaData raw responses are transient; final output is SQL JSONB-style contracts payload", "fetched_at_utc": _now_utc()}), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest)], dict(clean_result.row_counts), details={"underlying": snapshot.get("underlying"), "snapshot_time": snapshot.get("snapshot_time")}), SourcePayload(snapshot, int(clean_result.row_counts.get("option_chain_snapshot_contracts", 0)), fetch_result, clean_result)


def clean(context: BundleContext, payload: SourcePayload) -> tuple[StepResult, CleanedPayload]:
    row = {
        "run_id": str(context.metadata["run_id"]),
        "task_id": str(context.task_key.get("task_id") or ""),
        "underlying": str(payload.snapshot.get("underlying") or ""),
        "snapshot_time": str(payload.snapshot.get("snapshot_time") or ""),
        "contract_count": int(payload.snapshot.get("contract_count") or payload.contract_count),
        "contracts": payload.snapshot.get("contracts") or [],
    }
    result = StepResult("succeeded", [], {OUTPUT_TABLE: 1, "option_chain_snapshot_contracts": row["contract_count"]}, details={"columns": SQL_FIELDS, "table": OUTPUT_TABLE, "natural_key": KEY_COLUMNS})
    return result, CleanedPayload([row])


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


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None, sql_writer: SqlTableWriter | None = None):
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, source_payload = fetch(context, client=client)
        clean_result, cleaned_payload = clean(context, source_payload)
        save_result = save(context, clean_result, cleaned_payload, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
