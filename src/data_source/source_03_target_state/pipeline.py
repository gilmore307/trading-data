"""Deterministic m03 target-state data-acquisition normalizer.

This source consumes already-available target-local bar and liquidity evidence for
anonymous target candidates. It performs no provider calls and does not persist
raw bulky inputs; callers either pass local rows/paths or write the normalized SQL
surface directly through a reviewed writer.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from feed_availability.sanitize import sanitize_value
from data_runtime.config import resolve_output_root
from data_runtime.io import write_receipt_bundle
from storage.sql import PostgresSqlTableWriter, SqlTableWriter

SOURCE = "m03_target_state_vector_data_acquisition"
LEGACY_SOURCE = "source_03_target_state"
MODEL_ID = "target_state_vector_model"
OUTPUT_TABLE = SOURCE
ET = ZoneInfo("America/New_York")
SQL_FIELDS = [
    "target_candidate_id",
    "symbol",
    "timeframe",
    "timestamp",
    "available_time",
    "bar_open",
    "bar_high",
    "bar_low",
    "bar_close",
    "bar_volume",
    "bar_vwap",
    "bar_trade_count",
    "dollar_volume",
    "quote_count",
    "avg_bid",
    "avg_ask",
    "avg_bid_size",
    "avg_ask_size",
    "avg_spread",
    "spread_bps",
    "last_bid",
    "last_ask",
]
KEY_COLUMNS = ["target_candidate_id", "timeframe", "timestamp"]


@dataclass(frozen=True)
class SourceContext:
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
    candidate_rows: list[dict[str, Any]]
    bar_rows: list[dict[str, Any]]
    liquidity_rows: list[dict[str, Any]]


@dataclass(frozen=True)
class CleanedPayload:
    rows: list[dict[str, Any]]


class TargetStateSourceError(ValueError):
    """Raised for invalid target-state source inputs."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> SourceContext:
    if task_key.get("source") not in {SOURCE, LEGACY_SOURCE}:
        raise TargetStateSourceError(f"task_key.source must be {SOURCE}")
    output_root = resolve_output_root(task_key, default_task_id=f"{SOURCE}_task")
    return SourceContext(task_key, output_root / "runs" / run_id, output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def fetch(context: SourceContext) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    candidate_rows = _load_rows(params, inline_keys=("target_candidates", "target_candidate_rows", "candidate_rows"), path_keys=("target_candidates_path", "candidate_rows_path"))
    bar_rows = _load_rows(params, inline_keys=("bar_rows", "bars"), path_keys=("bar_rows_path", "bars_path", "bars_csv_path", "bars_json_path"))
    liquidity_rows = _load_rows(params, inline_keys=("liquidity_rows", "liquidity_bars"), path_keys=("liquidity_rows_path", "liquidity_bars_path", "liquidity_csv_path", "liquidity_json_path"))
    if not bar_rows and not liquidity_rows:
        raise TargetStateSourceError("params.bar_rows/bars or params.liquidity_rows/liquidity_bars are required")

    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": SOURCE,
        "model_id": MODEL_ID,
        "task_id": context.task_key.get("task_id"),
        "run_id": context.metadata.get("run_id"),
        "input_counts": {"candidate_rows": len(candidate_rows), "bar_rows": len(bar_rows), "liquidity_rows": len(liquidity_rows)},
        "output_table": OUTPUT_TABLE,
        "output_columns": SQL_FIELDS,
        "raw_persistence": "not_persisted_by_default; source_03_target_state normalizes caller-supplied local/SQL-safe rows only",
        "fetched_at_utc": _now_utc(),
    }
    path = context.run_dir / "request_manifest.json"
    path.write_text(json.dumps(sanitize_value(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path)], {"input_rows_transient": len(candidate_rows) + len(bar_rows) + len(liquidity_rows)}, details=manifest), SourcePayload(candidate_rows, bar_rows, liquidity_rows)


def _load_rows(params: Mapping[str, Any], *, inline_keys: tuple[str, ...], path_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    for key in inline_keys:
        if key in params and params[key] not in (None, ""):
            return _coerce_rows(params[key], source=key)
    for key in path_keys:
        if key in params and params[key] not in (None, ""):
            return _read_rows_path(Path(str(params[key])))
    return []


def _coerce_rows(value: Any, *, source: str) -> list[dict[str, Any]]:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("[") or stripped.startswith("{"):
            return _coerce_rows(json.loads(stripped), source=source)
        return _read_rows_path(Path(stripped))
    if isinstance(value, Mapping):
        for key in ("rows", "bars", "liquidity_rows", "target_candidates", "candidate_rows"):
            if isinstance(value.get(key), list):
                return [dict(row) for row in value[key]]
        return [dict(value)]
    if isinstance(value, Iterable):
        return [dict(row) for row in value]
    raise TargetStateSourceError(f"{source} must be rows, a JSON object/list, or a CSV/JSON path")


def _read_rows_path(path: Path) -> list[dict[str, Any]]:
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise TargetStateSourceError(f"input path does not exist: {path}")
    if path.suffix.lower() in {".json", ".jsonl", ".ndjson"}:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() in {".jsonl", ".ndjson"}:
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        return _coerce_rows(json.loads(text), source=str(path))
    with path.open(newline="", encoding="utf-8") as handle:
        return [{str(k): v for k, v in row.items()} for row in csv.DictReader(handle)]


def clean(context: SourceContext, payload: SourcePayload) -> tuple[StepResult, CleanedPayload]:
    params = dict(context.task_key.get("params") or {})
    default_timeframe = _normalize_timeframe(str(params.get("timeframe") or "1Min"))
    start = _parse_optional_ts(params.get("start"))
    end = _parse_optional_ts(params.get("end"))
    candidates = _candidate_map(payload.candidate_rows)
    rows_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped = {"missing_candidate": 0, "missing_timestamp": 0, "outside_window": 0}

    for raw in payload.bar_rows:
        row = _base_row(raw, candidates, default_timeframe=default_timeframe)
        if row is None:
            skipped["missing_candidate"] += 1
            continue
        if not _within_window(row["timestamp"], start, end):
            skipped["outside_window"] += 1
            continue
        _project_bar_fields(row, raw)
        key = _row_key(row)
        rows_by_key[key] = _merge_non_null(rows_by_key.get(key, {}), row)

    for raw in payload.liquidity_rows:
        try:
            row = _base_row(raw, candidates, default_timeframe=default_timeframe, timestamp_keys=("timestamp", "interval_start", "available_time"))
        except TargetStateSourceError:
            skipped["missing_timestamp"] += 1
            continue
        if row is None:
            skipped["missing_candidate"] += 1
            continue
        if not _within_window(row["timestamp"], start, end):
            skipped["outside_window"] += 1
            continue
        _project_bar_fields(row, raw)
        _project_liquidity_fields(row, raw)
        key = _row_key(row)
        rows_by_key[key] = _merge_non_null(rows_by_key.get(key, {}), row)

    rows = [_finalize_row(row) for row in rows_by_key.values()]
    rows.sort(key=lambda row: (row["target_candidate_id"], row["timeframe"], row["timestamp"]))
    if not rows:
        raise TargetStateSourceError("source_03_target_state produced zero candidate-mapped rows")
    result = StepResult(
        "succeeded",
        [],
        {OUTPUT_TABLE: len(rows)},
        details={"columns": SQL_FIELDS, "natural_key": KEY_COLUMNS, "table": OUTPUT_TABLE, "skipped": skipped, "identity_boundary": "symbol is retained only as source/audit/routing metadata; model-facing feature blocks must use target_candidate_id"},
    )
    return result, CleanedPayload(rows)


def _merge_non_null(existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if value is not None:
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    return merged


def _candidate_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    candidates: dict[str, str] = {}
    for row in rows:
        target_candidate_id = str(row.get("target_candidate_id") or "").strip()
        symbol = str(row.get("symbol") or row.get("routing_symbol_ref") or row.get("audit_symbol_ref") or "").strip().upper()
        if target_candidate_id and symbol:
            candidates[symbol] = target_candidate_id
    return candidates


def _base_row(raw: Mapping[str, Any], candidates: Mapping[str, str], *, default_timeframe: str, timestamp_keys: tuple[str, ...] = ("timestamp", "available_time")) -> dict[str, Any] | None:
    symbol = str(raw.get("symbol") or raw.get("routing_symbol_ref") or raw.get("audit_symbol_ref") or "").strip().upper()
    target_candidate_id = str(raw.get("target_candidate_id") or "").strip() or candidates.get(symbol, "")
    if not target_candidate_id:
        return None
    timestamp_value = _first_present(raw, *timestamp_keys)
    if timestamp_value in (None, ""):
        raise TargetStateSourceError("timestamp is required")
    timestamp = _parse_ts(timestamp_value).isoformat()
    available_time = _parse_ts(raw.get("available_time") or timestamp).isoformat()
    return {
        "target_candidate_id": target_candidate_id,
        "symbol": symbol,
        "timeframe": _normalize_timeframe(str(raw.get("timeframe") or default_timeframe)),
        "timestamp": timestamp,
        "available_time": available_time,
    }


def _project_bar_fields(row: dict[str, Any], raw: Mapping[str, Any]) -> None:
    row.update(
        {
            "bar_open": _number(_first_present(raw, "bar_open", "open")),
            "bar_high": _number(_first_present(raw, "bar_high", "high")),
            "bar_low": _number(_first_present(raw, "bar_low", "low")),
            "bar_close": _number(_first_present(raw, "bar_close", "close", "last_trade_price")),
            "bar_volume": _number(_first_present(raw, "bar_volume", "volume")),
            "bar_vwap": _number(_first_present(raw, "bar_vwap", "vwap")),
            "bar_trade_count": _integer(_first_present(raw, "bar_trade_count", "trade_count")),
        }
    )
    row["dollar_volume"] = _number(raw.get("dollar_volume"))


def _project_liquidity_fields(row: dict[str, Any], raw: Mapping[str, Any]) -> None:
    row.update(
        {
            "quote_count": _integer(raw.get("quote_count")),
            "avg_bid": _number(raw.get("avg_bid")),
            "avg_ask": _number(raw.get("avg_ask")),
            "avg_bid_size": _number(raw.get("avg_bid_size")),
            "avg_ask_size": _number(raw.get("avg_ask_size")),
            "avg_spread": _number(raw.get("avg_spread")),
            "spread_bps": _number(raw.get("spread_bps")),
            "last_bid": _number(raw.get("last_bid")),
            "last_ask": _number(raw.get("last_ask")),
        }
    )


def _finalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    output = {column: row.get(column) for column in SQL_FIELDS}
    if output["dollar_volume"] is None:
        close = _number(output.get("bar_close"))
        volume = _number(output.get("bar_volume"))
        output["dollar_volume"] = close * volume if close is not None and volume is not None else None
    if output["spread_bps"] is None:
        spread = _number(output.get("avg_spread"))
        anchor = _number(output.get("bar_close")) or _avg_mid(output)
        output["spread_bps"] = None if spread is None or anchor in (None, 0) else spread / anchor * 10000
    return output


def _avg_mid(row: Mapping[str, Any]) -> float | None:
    bid = _number(row.get("avg_bid"))
    ask = _number(row.get("avg_ask"))
    return None if bid is None or ask is None else (bid + ask) / 2


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return str(row["target_candidate_id"]), str(row["timeframe"]), str(row["timestamp"])


def _first_present(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_timeframe(value: str) -> str:
    mapping = {"1m": "1Min", "1min": "1Min", "1minute": "1Min", "5m": "5Min", "5min": "5Min", "15m": "15Min", "15min": "15Min", "60m": "1Hour", "1h": "1Hour", "1hour": "1Hour", "1d": "1Day", "day": "1Day", "daily": "1Day"}
    return mapping.get(value.strip().lower(), value.strip() or "1Min")


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET)


def _parse_optional_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    return _parse_ts(value)


def _within_window(timestamp: str, start: datetime | None, end: datetime | None) -> bool:
    parsed = _parse_ts(timestamp)
    return (start is None or parsed >= start) and (end is None or parsed < end)


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def save(context: SourceContext, clean_result: StepResult, payload: CleanedPayload, *, sql_writer: SqlTableWriter | None = None) -> StepResult:
    writer = sql_writer or PostgresSqlTableWriter.from_config({})
    metadata = writer.write_rows(table=OUTPUT_TABLE, columns=SQL_FIELDS, rows=payload.rows, key_columns=KEY_COLUMNS)
    reference = str(metadata.get("qualified_table") or metadata.get("table") or OUTPUT_TABLE)
    return StepResult("succeeded", [reference], dict(clean_result.row_counts), details={"format": "sql_table", "table": OUTPUT_TABLE, "columns": SQL_FIELDS, "storage": metadata})


def write_receipt(context: SourceContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: Exception | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "source": SOURCE, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": str(context.metadata["run_id"]), "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != entry["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "source": SOURCE})
    write_receipt_bundle(context.receipt_path, context.run_dir, existing)
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": entry["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str, sql_writer: SqlTableWriter | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, source_payload = fetch(context)
        clean_result, cleaned_payload = clean(context, source_payload)
        save_result = save(context, clean_result, cleaned_payload, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except Exception as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
