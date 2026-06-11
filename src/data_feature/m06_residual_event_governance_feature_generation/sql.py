"""SQL wrapper for m06_residual_event_governance_feature_generation production."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from data_runtime.config import database_url_file

from .generator import generate_rows

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COLUMNS = (
    "run_id",
    "source_run_ref",
    "event_id",
    "canonical_event_id",
    "event_time",
    "available_time",
    "feature_payload_json",
    "feature_quality_diagnostics",
)
KEY_COLUMNS = ("event_id",)
JSONB_COLUMNS = {"feature_payload_json", "feature_quality_diagnostics"}


def _database_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.environ.get("OPENCLAW_DATABASE_URL"):
        return os.environ["OPENCLAW_DATABASE_URL"]
    path = database_url_file()
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    raise SystemExit(f"database URL not supplied and {path} does not exist")


def _quote(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"unsafe SQL identifier: {identifier!r}")
    return '"' + identifier.replace('"', '""') + '"'


def _qualified(schema: str, table: str) -> str:
    return f"{_quote(schema)}.{_quote(table)}"


def fetch_source_rows(cursor: Any, *, source_schema: str, source_table: str, source_start: str | None = None, source_end: str | None = None) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if source_start:
        where.append("available_time >= %s")
        params.append(source_start)
    if source_end:
        where.append("available_time < %s")
        params.append(source_end)
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    cursor.execute(
        f"""
        SELECT event_id, canonical_event_id, dedup_status, source_priority, coverage_reason, covered_by_event_id,
               event_time, available_time, information_role_type, event_category_type, scope_type, symbol, sector_type,
               title, summary, source_name, reference_type, reference, source_artifact_path
        FROM {_qualified(source_schema, source_table)}
        {where_sql}
        ORDER BY available_time ASC, event_id ASC
        """,
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def write_feature_rows_sql(cursor: Any, rows: Sequence[Mapping[str, Any]], *, target_schema: str, target_table: str) -> None:
    if not rows:
        return
    qualified = _qualified(target_schema, target_table)
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote(target_schema)}")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {qualified} (
          "run_id" TEXT NOT NULL,
          "source_run_ref" TEXT NOT NULL,
          "event_id" TEXT NOT NULL,
          "canonical_event_id" TEXT NOT NULL,
          "event_time" TIMESTAMPTZ,
          "available_time" TIMESTAMPTZ NOT NULL,
          "feature_payload_json" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          "feature_quality_diagnostics" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          PRIMARY KEY ("event_id")
        )
        """
    )
    placeholders = ["%s::jsonb" if column in JSONB_COLUMNS else "%s" for column in COLUMNS]
    update_columns = [column for column in COLUMNS if column not in KEY_COLUMNS]
    insert_sql = f"""
        INSERT INTO {qualified} ({", ".join(_quote(column) for column in COLUMNS)})
        VALUES ({", ".join(placeholders)})
        ON CONFLICT ({", ".join(_quote(column) for column in KEY_COLUMNS)}) DO UPDATE SET
          {", ".join(f'{_quote(column)} = EXCLUDED.{_quote(column)}' for column in update_columns)}
    """
    for row in rows:
        values = [json.dumps(row.get(column) or {}, sort_keys=True, default=str) if column in JSONB_COLUMNS else row.get(column) for column in COLUMNS]
        cursor.execute(insert_sql, values)


def generate_sql(*, database_url: str, source_schema: str, source_table: str, target_schema: str, target_table: str, source_start: str | None, source_end: str | None, run_id: str) -> int:
    import psycopg  # type: ignore
    from psycopg.rows import dict_row  # type: ignore

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            source_rows = fetch_source_rows(cursor, source_schema=source_schema, source_table=source_table, source_start=source_start, source_end=source_end)
            rows = generate_rows(source_rows, run_id=run_id)
            write_feature_rows_sql(cursor, rows, target_schema=target_schema, target_table=target_table)
            return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url")
    parser.add_argument("--source-schema", default="trading_data")
    parser.add_argument("--source-table", default="model_06_residual_event_governance_data_acquisition")
    parser.add_argument("--target-schema", default="trading_data")
    parser.add_argument("--target-table", default="model_06_residual_event_governance_feature_generation")
    parser.add_argument("--source-start")
    parser.add_argument("--source-end")
    parser.add_argument("--run-id", default="model_06_residual_event_governance_feature_generation_sql")
    args = parser.parse_args(argv)
    count = generate_sql(database_url=_database_url(args.database_url), source_schema=args.source_schema, source_table=args.source_table, target_schema=args.target_schema, target_table=args.target_table, source_start=args.source_start, source_end=args.source_end, run_id=args.run_id)
    print(f"generated {count} rows into {args.target_schema}.{args.target_table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
