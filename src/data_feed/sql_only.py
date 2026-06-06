"""Shared helpers for SQL-only feed outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from data_runtime.io import atomic_write_json
from storage.sql import PostgresSqlTableWriter, SqlTableWriter


def compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def sql_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return compact_json(value)
    return value


def sql_rows(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> list[dict[str, Any]]:
    return [{field: sql_value(row.get(field)) for field in fields} for row in rows]


def with_row_id(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], *, namespace: str) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        payload = {field: sql_value(row.get(field)) for field in fields}
        digest = hashlib.sha256(f"{namespace}:{compact_json(payload)}".encode("utf-8")).hexdigest()
        output.append({"row_id": digest, **payload})
    return output


def write_schema(run_dir: Path, data_kind: str, fields: Sequence[str], *, row_count: int) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "schema.json"
    atomic_write_json(
        path,
        {
            data_kind: list(fields),
            "retention": "sql_only_no_jsonl_or_csv_payload",
            "row_count": row_count,
        },
    )
    return path


def write_table(
    *,
    table: str,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    key_columns: Sequence[str],
    sql_writer: SqlTableWriter | None,
) -> dict[str, Any]:
    writer = sql_writer or PostgresSqlTableWriter.from_config({})
    if rows:
        return writer.write_rows(table=table, columns=columns, rows=rows, key_columns=key_columns)
    return {
        "table": table,
        "qualified_table": table,
        "rows_written": 0,
        "driver": "postgresql",
        "storage_target_id": "trading_data_postgres",
    }


def sql_reference(metadata: Mapping[str, Any]) -> str:
    return str(metadata.get("qualified_table") or metadata.get("table") or "")
