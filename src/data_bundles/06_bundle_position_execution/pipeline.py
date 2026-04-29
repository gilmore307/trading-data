"""Manager-facing 06 PositionExecutionModel selected option time-series bundle."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from data_sources.thetadata_option_primary_tracking.pipeline import run as run_option_tracking
from source_availability.http import HttpClient
from source_availability.sanitize import sanitize_value
from storage.sql import PostgresSqlTableWriter, SqlTableWriter

BUNDLE = "06_bundle_position_execution"
MODEL_ID = "position_execution_model"
OUTPUT_TABLE = "bundle_06_position_execution"
ET = ZoneInfo("America/New_York")
DEFAULT_TIMEFRAME = "1Min"
EXIT_EXTENSION_HOURS = 1
SQL_FIELDS = [
    "underlying",
    "option_symbol",
    "expiration",
    "option_right_type",
    "strike",
    "timeframe",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "trade_count",
    "vwap",
]
KEY_COLUMNS = ["option_symbol", "timeframe", "timestamp"]


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
    contracts: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    source_receipts: list[str]


@dataclass(frozen=True)
class CleanedPayload:
    rows: list[dict[str, Any]]


class PositionExecutionInputsError(ValueError):
    """Raised for invalid PositionExecutionModel input tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise PositionExecutionInputsError(f"params.{key} is required")
    return value


def _as_list(value: Any) -> list[Any]:
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return value
    return [value]


def _et_dt(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PositionExecutionInputsError(f"invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET)


def _date(value: Any) -> str:
    return _et_dt(value).date().isoformat()


def _right(contract: Mapping[str, Any]) -> str:
    value = str(contract.get("option_right_type") or contract.get("right") or "").upper()
    aliases = {"C": "CALL", "CALL": "CALL", "P": "PUT", "PUT": "PUT"}
    if value not in aliases:
        raise PositionExecutionInputsError("selected contract requires option_right_type/right CALL or PUT")
    return aliases[value]


def _option_symbol(contract: Mapping[str, Any]) -> str:
    explicit = str(contract.get("option_symbol") or "").strip().upper()
    if explicit:
        return explicit
    underlying = str(_required(contract, "underlying")).upper()
    expiration = str(_required(contract, "expiration"))
    right = _right(contract)[0]
    strike = float(_required(contract, "strike"))
    return f"{underlying}_{expiration}_{right}_{strike:g}"


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise PositionExecutionInputsError(f"task_key.bundle must be {BUNDLE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    return BundleContext(task_key, output_root / "runs" / run_id, output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _fetch_contract_rows(context: BundleContext, contract: Mapping[str, Any], *, client: HttpClient | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    inline = _as_list(contract.get("option_rows") or contract.get("timeseries_rows"))
    if inline:
        return [dict(row) for row in inline if isinstance(row, Mapping)], []

    timeframe = str(contract.get("timeframe") or DEFAULT_TIMEFRAME)
    source_task = {
        "task_id": f"{context.task_key.get('task_id')}_{_option_symbol(contract)}_tracking",
        "bundle": "thetadata_option_primary_tracking",
        "params": {
            "underlying": str(_required(contract, "underlying")).upper(),
            "expiration": str(_required(contract, "expiration")),
            "right": _right(contract),
            "strike": float(_required(contract, "strike")),
            "start_date": _date(_required(contract, "entry_time")),
            "end_date": _date(_et_dt(_required(contract, "exit_time")) + timedelta(hours=EXIT_EXTENSION_HOURS)),
            "timeframe": timeframe,
        },
        "output_root": str(context.run_dir / "source" / _option_symbol(contract)),
    }
    for passthrough in ("thetadata_base_url", "timeout_seconds", "registry_csv"):
        if passthrough in contract:
            source_task["params"][passthrough] = contract[passthrough]
    result = run_option_tracking(source_task, run_id=str(context.metadata["run_id"]), client=client)
    if result.status != "succeeded":
        raise PositionExecutionInputsError(f"option tracking failed for {_option_symbol(contract)}: {result.details.get('error')}")
    output_refs = [ref for ref in result.references if ref.endswith("option_bar.csv")]
    rows = _read_csv(Path(output_refs[0])) if output_refs else []
    return rows, result.references


def fetch(context: BundleContext, *, client: HttpClient | None = None) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    contracts = [dict(item) for item in _as_list(_required(params, "selected_contracts")) if isinstance(item, Mapping)]
    if not contracts:
        raise PositionExecutionInputsError("params.selected_contracts must contain at least one contract")
    rows: list[dict[str, Any]] = []
    refs: list[str] = []
    for contract in contracts:
        contract_rows, contract_refs = _fetch_contract_rows(context, contract, client=client)
        option_symbol = _option_symbol(contract)
        for row in contract_rows:
            row.setdefault("underlying", str(contract.get("underlying") or "").upper())
            row.setdefault("option_symbol", option_symbol)
            row.setdefault("expiration", contract.get("expiration"))
            row.setdefault("option_right_type", _right(contract))
            row.setdefault("strike", contract.get("strike"))
            row.setdefault("timeframe", contract.get("timeframe") or DEFAULT_TIMEFRAME)
            row.setdefault("entry_time", contract.get("entry_time"))
            row.setdefault("exit_time", contract.get("exit_time"))
            rows.append(row)
        refs.extend(contract_refs)
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(json.dumps(sanitize_value({"bundle": BUNDLE, "model_id": MODEL_ID, "contract_count": len(contracts), "row_count": len(rows), "source_receipts": refs, "fetched_at_utc": _now_utc()}), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest), *refs], {"raw_option_timeseries_rows": len(rows)}, details={"contract_count": len(contracts)}), SourcePayload(contracts, rows, refs)


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None


def clean(context: BundleContext, payload: SourcePayload) -> tuple[StepResult, CleanedPayload]:
    rows: list[dict[str, Any]] = []
    for row in payload.rows:
        timestamp_value = row.get("timestamp")
        if timestamp_value in (None, ""):
            continue
        timestamp = _et_dt(timestamp_value)
        entry = _et_dt(row.get("entry_time")) if row.get("entry_time") else None
        exit_plus = _et_dt(row.get("exit_time")) + timedelta(hours=EXIT_EXTENSION_HOURS) if row.get("exit_time") else None
        if entry and timestamp < entry:
            continue
        if exit_plus and timestamp > exit_plus:
            continue
        cleaned = {
            "underlying": str(row.get("underlying") or "").upper(),
            "option_symbol": str(row.get("option_symbol") or "").upper(),
            "expiration": str(row.get("expiration") or ""),
            "option_right_type": _right(row),
            "strike": _num(row.get("strike")),
            "timeframe": str(row.get("timeframe") or DEFAULT_TIMEFRAME),
            "timestamp": timestamp.isoformat(),
            "open": _num(row.get("open")),
            "high": _num(row.get("high")),
            "low": _num(row.get("low")),
            "close": _num(row.get("close")),
            "volume": _num(row.get("volume")),
            "trade_count": _int(row.get("trade_count") or row.get("count")),
            "vwap": _num(row.get("vwap")),
        }
        if not cleaned["option_symbol"]:
            cleaned["option_symbol"] = _option_symbol(cleaned)
        rows.append(cleaned)
    rows.sort(key=lambda item: (item["option_symbol"], item["timeframe"], item["timestamp"]))
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


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None, sql_writer: SqlTableWriter | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, source_payload = fetch(context, client=client)
        clean_result, cleaned_payload = clean(context, source_payload)
        save_result = save(context, clean_result, cleaned_payload, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
