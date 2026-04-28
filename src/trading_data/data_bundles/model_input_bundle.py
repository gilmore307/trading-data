"""Shared runner for model-input bundle manifests.

These bundles are manager-facing orchestration surfaces. They do not fetch raw
provider data directly; they collect already-produced source/derived artifacts
into a point-in-time model-input manifest for the named model layer.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from trading_data.data_bundles.config import load_bundle_config
from trading_data.source_availability.sanitize import sanitize_value

FIELDS = [
    "bundle",
    "model_id",
    "as_of_et",
    "input_role",
    "data_kind",
    "path",
    "required",
    "point_in_time",
    "notes",
]


@dataclass(frozen=True)
class BundleSpec:
    bundle: str
    model_id: str
    output_name: str


@dataclass(frozen=True)
class BundleContext:
    task_key: dict[str, Any]
    run_dir: Path
    cleaned_dir: Path
    saved_dir: Path
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
    config: dict[str, Any]
    inputs: dict[str, list[str]]


class ModelInputBundleError(ValueError):
    """Raised for invalid model-input bundle tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _listify(value: Any) -> list[str]:
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def build_context(spec: BundleSpec, task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != spec.bundle:
        raise ModelInputBundleError(f"task_key.bundle must be {spec.bundle}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', spec.bundle + '_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def fetch(spec: BundleSpec, context: BundleContext) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    config_path = str(params.get("config_path") or "") or None
    config = load_bundle_config(spec.bundle, config_path=config_path)
    explicit_inputs = params.get("input_paths") or {}
    if explicit_inputs and not isinstance(explicit_inputs, Mapping):
        raise ModelInputBundleError("params.input_paths must be an object mapping input_role to one path or list of paths")
    inputs: dict[str, list[str]] = {}
    for role, value in dict(explicit_inputs).items():
        inputs[str(role)] = _listify(value)
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "bundle": spec.bundle,
        "model_id": spec.model_id,
        "config": config_path or "bundle-local config.json",
        "input_roles": sorted(inputs),
        "raw_persistence": "not_applicable; model-input bundles compose saved source/derived artifacts",
        "fetched_at_utc": _now_utc(),
    }
    path = context.run_dir / "request_manifest.json"
    path.write_text(json.dumps(sanitize_value(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path)], {"input_artifact_ref": sum(len(paths) for paths in inputs.values())}, details=manifest), SourcePayload(config, inputs)


def clean(spec: BundleSpec, context: BundleContext, payload: SourcePayload) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    as_of_et = str(params.get("as_of_et") or params.get("available_time_et") or "")
    if not as_of_et:
        raise ModelInputBundleError("params.as_of_et is required for point-in-time model-input bundles")
    configured_inputs = payload.config.get("inputs") or []
    rows: list[dict[str, str]] = []
    if not isinstance(configured_inputs, list):
        raise ModelInputBundleError("bundle config field inputs must be a list")
    for item in configured_inputs:
        if not isinstance(item, Mapping):
            continue
        role = str(item.get("role") or "").strip()
        data_kind = str(item.get("data_kind") or "").strip()
        if not role or not data_kind:
            raise ModelInputBundleError("each configured input requires role and data_kind")
        paths = payload.inputs.get(role) or []
        if not paths and item.get("required", True):
            raise ModelInputBundleError(f"missing required params.input_paths.{role}")
        if not paths:
            rows.append(_row(spec, as_of_et, role, data_kind, "", item))
        for path in paths:
            rows.append(_row(spec, as_of_et, role, data_kind, path, item))
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    output = context.cleaned_dir / f"{spec.output_name}.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    schema = context.cleaned_dir / "schema.json"
    schema.write_text(json.dumps({spec.output_name: FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(output), str(schema)], {spec.output_name: len(rows)}, details={"columns": FIELDS})


def _row(spec: BundleSpec, as_of_et: str, role: str, data_kind: str, path: str, item: Mapping[str, Any]) -> dict[str, str]:
    return {
        "bundle": spec.bundle,
        "model_id": spec.model_id,
        "as_of_et": as_of_et,
        "input_role": role,
        "data_kind": data_kind,
        "path": path,
        "required": str(bool(item.get("required", True))).lower(),
        "point_in_time": str(bool(item.get("point_in_time", True))).lower(),
        "notes": str(item.get("notes") or ""),
    }


def save(spec: BundleSpec, context: BundleContext, clean_result: StepResult) -> StepResult:
    rows = [json.loads(line) for line in (context.cleaned_dir / f"{spec.output_name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / f"{spec.output_name}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return StepResult("succeeded", [str(path)], dict(clean_result.row_counts), details={"format": "csv", "columns": FIELDS})


def write_receipt(spec: BundleSpec, context: BundleContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: BaseException | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "bundle": spec.bundle, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": str(context.metadata["run_id"]), "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != entry["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "bundle": spec.bundle})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": entry["run_id"], "error": entry["error"]})


def run_bundle(spec: BundleSpec, task_key: dict[str, Any], *, run_id: str) -> StepResult:
    context = build_context(spec, task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, payload = fetch(spec, context)
        clean_result = clean(spec, context, payload)
        save_result = save(spec, context, clean_result)
        return write_receipt(spec, context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(spec, context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
