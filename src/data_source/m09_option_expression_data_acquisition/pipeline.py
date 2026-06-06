"""Manager-facing M09 OptionExpressionModel option snapshot input source."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from data_source.option_chain_state_source import pipeline as option_chain_source
from feed_availability.http import HttpClient, RetryPolicy
from feed_availability.sanitize import sanitize_value
from data_runtime.config import resolve_output_root
from data_runtime.io import write_receipt_bundle
from storage.sql import PostgresSqlTableReader, PostgresSqlTableWriter, SqlTableReader, SqlTableWriter

SOURCE = "m09_option_expression_data_acquisition"
MODEL_ID = "option_expression_model"
OUTPUT_TABLE = SOURCE
DEFAULT_MAX_DTE = 45
DEFAULT_STRIKE_RANGE = 5
DEFAULT_OPTION_BUCKET_POLICY_REF = "LAYER_09_OPTION_BUCKET_STRIKE_POLICY"
SQL_FIELDS = [
    "underlying",
    "snapshot_time",
    "snapshot_type",
    "option_symbol",
    "expiration",
    "option_right_type",
    "strike",
    "bid",
    "ask",
    "mid",
    "spread",
    "spread_pct",
    "bid_size",
    "ask_size",
    "bid_exchange",
    "ask_exchange",
    "bid_condition",
    "ask_condition",
    "implied_vol",
    "iv_error",
    "delta",
    "theta",
    "vega",
    "rho",
    "epsilon",
    "lambda",
    "underlying_price",
    "underlying_timestamp",
    "days_to_expiration",
]
KEY_COLUMNS = ["underlying", "snapshot_time", "snapshot_type", "option_symbol"]


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
    rows: list[dict[str, Any]]
    fetch_result: StepResult
    clean_result: StepResult


@dataclass(frozen=True)
class CleanedPayload:
    rows: list[dict[str, Any]]
    shared_rows: list[dict[str, Any]]


class OptionExpressionInputsError(ValueError):
    """Raised for invalid OptionExpressionModel input tasks."""


def _is_missing_sql_table_error(exc: Exception) -> bool:
    return exc.__class__.__name__ == "UndefinedTable" or "does not exist" in str(exc)


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> SourceContext:
    if task_key.get("source") != SOURCE:
        raise OptionExpressionInputsError(f"task_key.source must be {SOURCE}")
    output_root = resolve_output_root(task_key, default_task_id=f"{SOURCE}_task")
    return SourceContext(task_key, output_root / "runs" / run_id, output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _snapshot_type(params: Mapping[str, Any]) -> str:
    value = str(params.get("snapshot_type") or "entry").strip().lower()
    if value not in {"entry", "exit"}:
        raise OptionExpressionInputsError("params.snapshot_type must be 'entry' or 'exit'")
    return value


def _read_shared_source_rows(params: Mapping[str, Any], *, sql_reader: SqlTableReader | None = None) -> list[dict[str, Any]]:
    if params.get("reuse_option_chain_state_source") is False:
        return []
    underlying = str(params.get("underlying") or "").strip().upper()
    snapshot_time = str(params.get("snapshot_time") or "").strip()
    if not underlying or not snapshot_time:
        return []
    reader = sql_reader or PostgresSqlTableReader.from_config(params)
    window_start = params.get("window_start")
    window_end = params.get("window_end")
    time_column = "snapshot_time" if window_start and window_end else None
    where_equals = {"underlying": underlying} if time_column else {"underlying": underlying, "snapshot_time": snapshot_time}
    try:
        rows = reader.read_rows(
            table=option_chain_source.OUTPUT_TABLE,
            columns=option_chain_source.SQL_FIELDS,
            where_equals=where_equals,
            time_column=time_column,
            start=window_start if time_column else None,
            end=window_end if time_column else None,
            order_by=("snapshot_time", "expiration", "option_right_type", "strike", "option_symbol"),
        )
    except Exception as exc:
        if _is_missing_sql_table_error(exc):
            return []
        raise
    return [dict(row) for row in rows]


def fetch(
    context: SourceContext,
    *,
    client: HttpClient | None = None,
    sql_reader: SqlTableReader | None = None,
    client_is_fixture: bool = False,
) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    snapshot_type = _snapshot_type(params)
    shared_rows: list[dict[str, Any]] = []
    if not client_is_fixture:
        shared_rows = _read_shared_source_rows(params, sql_reader=sql_reader)
    if shared_rows:
        context.run_dir.mkdir(parents=True, exist_ok=True)
        manifest = context.run_dir / "request_manifest.json"
        manifest.write_text(
            json.dumps(
                sanitize_value(
                    {
                        "source": SOURCE,
                        "model_id": MODEL_ID,
                        "input_source": option_chain_source.SOURCE,
                        "input_source_mode": "reused_sql_rows",
                        "params": {
                            "underlying": params.get("underlying"),
                            "snapshot_time": params.get("snapshot_time"),
                            "snapshot_type": snapshot_type,
                        },
                        "raw_persistence": "Layer 9 reused existing contract-level option_chain_state_source SQL rows",
                        "fetched_at_utc": _now_utc(),
                    }
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        fetch_result = StepResult(
            "succeeded",
            [str(manifest)],
            {option_chain_source.OUTPUT_TABLE: len(shared_rows), "option_chain_snapshot_contracts": len(shared_rows)},
            details={
                "underlying": params.get("underlying"),
                "snapshot_time": params.get("snapshot_time"),
                "snapshot_type": snapshot_type,
                "input_source": option_chain_source.SOURCE,
                "input_source_mode": "reused_sql_rows",
                "provider_calls": 0,
            },
        )
        return fetch_result, SourcePayload(shared_rows, fetch_result, StepResult("succeeded"))
    source_task = {
        "task_id": f"{context.task_key.get('task_id')}_option_chain_state_source",
        "source": option_chain_source.SOURCE,
        "params": params,
        "output_root": str(context.run_dir / "source" / option_chain_source.SOURCE),
        "manager_controls": context.task_key.get("manager_controls"),
    }
    source_context = option_chain_source.build_context(source_task, str(context.metadata["run_id"]))
    fetch_result, source_payload = option_chain_source.fetch(source_context, client=client, client_is_fixture=client_is_fixture)
    clean_result, cleaned_source = option_chain_source.clean(source_context, source_payload)
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(
        json.dumps(
            sanitize_value(
                {
                    "source": SOURCE,
                    "model_id": MODEL_ID,
                    "input_source": option_chain_source.SOURCE,
                    "input_source_mode": "provider_fetch",
                    "params": {
                        "underlying": params.get("underlying"),
                        "snapshot_time": params.get("snapshot_time"),
                        "snapshot_type": snapshot_type,
                        "max_dte": params.get("max_dte", DEFAULT_MAX_DTE),
                        "strike_range": params.get("strike_range", DEFAULT_STRIKE_RANGE),
                        "option_bucket_policy_ref": params.get("option_bucket_policy_ref", DEFAULT_OPTION_BUCKET_POLICY_REF),
                    },
                    "feed_fetch": asdict(fetch_result),
                    "feed_clean": asdict(clean_result),
                    "raw_persistence": "ThetaData raw responses are transient; final output is contract-level SQL rows",
                    "fetched_at_utc": _now_utc(),
                }
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return (
        StepResult(
            "succeeded",
            [str(manifest)],
            dict(clean_result.row_counts),
            details={
                "underlying": params.get("underlying"),
                "snapshot_time": params.get("snapshot_time"),
                "snapshot_type": snapshot_type,
                "input_source": option_chain_source.SOURCE,
                "input_source_mode": "provider_fetch",
            },
        ),
        SourcePayload(cleaned_source.rows, fetch_result, clean_result),
    )


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _layer_nine_row(snapshot_type: str, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "underlying": str(row.get("underlying") or ""),
        "snapshot_time": str(row.get("snapshot_time") or ""),
        "snapshot_type": snapshot_type,
        **{field: row.get(field) for field in SQL_FIELDS if field not in {"underlying", "snapshot_time", "snapshot_type"}},
    }


def clean(context: SourceContext, payload: SourcePayload) -> tuple[StepResult, CleanedPayload]:
    params = dict(context.task_key.get("params") or {})
    snapshot_type = _snapshot_type(params)
    rows = [_layer_nine_row(snapshot_type, row) for row in payload.rows]
    rows.sort(key=lambda row: (row["snapshot_time"], row["expiration"], row["option_right_type"], row["strike"] if row["strike"] is not None else -1, row["option_symbol"]))
    result = StepResult(
        "succeeded",
        [],
        {OUTPUT_TABLE: len(rows), option_chain_source.OUTPUT_TABLE: len(payload.rows), "option_chain_snapshot_contracts": len(rows)},
        details={"columns": SQL_FIELDS, "table": OUTPUT_TABLE, "natural_key": KEY_COLUMNS, "snapshot_type": snapshot_type, "input_source": option_chain_source.OUTPUT_TABLE},
    )
    return result, CleanedPayload(rows, payload.rows)


def save(context: SourceContext, clean_result: StepResult, payload: CleanedPayload, *, sql_writer: SqlTableWriter | None = None) -> StepResult:
    writer = sql_writer or PostgresSqlTableWriter.from_config({})
    shared_metadata = writer.write_rows(
        table=option_chain_source.OUTPUT_TABLE,
        columns=option_chain_source.SQL_FIELDS,
        rows=payload.shared_rows,
        key_columns=option_chain_source.KEY_COLUMNS,
    )
    metadata = writer.write_rows(table=OUTPUT_TABLE, columns=SQL_FIELDS, rows=payload.rows, key_columns=KEY_COLUMNS)
    reference = str(metadata.get("qualified_table") or metadata.get("table") or OUTPUT_TABLE)
    shared_reference = str(shared_metadata.get("qualified_table") or shared_metadata.get("table") or option_chain_source.OUTPUT_TABLE)
    return StepResult(
        "succeeded",
        [shared_reference, reference],
        dict(clean_result.row_counts),
        details={"format": "sql_table", "table": OUTPUT_TABLE, "columns": SQL_FIELDS, "storage": metadata, "shared_source_storage": shared_metadata},
    )


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


def run(
    task_key: dict[str, Any],
    *,
    run_id: str,
    client: HttpClient | None = None,
    sql_reader: SqlTableReader | None = None,
    sql_writer: SqlTableWriter | None = None,
    client_is_fixture: bool = False,
):
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, feed_payload = fetch(context, client=client, sql_reader=sql_reader, client_is_fixture=client_is_fixture)
        clean_result, cleaned_payload = clean(context, feed_payload)
        save_result = save(context, clean_result, cleaned_payload, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except Exception as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)


def _batch_run_id(task_key: Mapping[str, Any], *, batch_run_id: str, index: int) -> str:
    task_id = str(task_key.get("task_id") or f"{SOURCE}_task_{index:05d}")
    return f"{task_id}_{batch_run_id}"


def _batch_http_client(task_key: Mapping[str, Any]) -> HttpClient:
    return option_chain_source.batch_http_client(task_key)


def run_many(
    task_keys: list[dict[str, Any]],
    *,
    batch_run_id: str,
    continue_on_error: bool = False,
    client: HttpClient | None = None,
    sql_writer: SqlTableWriter | None = None,
    client_is_fixture: bool = False,
) -> dict[str, Any]:
    writer = sql_writer or PostgresSqlTableWriter.from_config({})
    shared_client = client or (_batch_http_client(task_keys[0]) if task_keys else None)
    items: list[dict[str, Any]] = []
    for index, task_key in enumerate(task_keys, start=1):
        result = run(
            task_key,
            run_id=_batch_run_id(task_key, batch_run_id=batch_run_id, index=index),
            client=shared_client,
            sql_writer=writer,
            client_is_fixture=client_is_fixture,
        )
        items.append(
            {
                "task_id": task_key.get("task_id"),
                "status": result.status,
                "row_counts": result.row_counts,
                "references": result.references,
                "details": result.details,
            }
        )
        if result.status != "succeeded" and not continue_on_error:
            break
    failed_count = sum(1 for item in items if item["status"] != "succeeded")
    return {
        "contract_type": "m09_option_expression_data_acquisition_batch_result",
        "batch_run_id": batch_run_id,
        "task_count": len(items),
        "succeeded_count": len(items) - failed_count,
        "failed_count": failed_count,
        "items": items,
    }
