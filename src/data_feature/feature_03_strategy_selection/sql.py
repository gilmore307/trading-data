"""Generate feature_03_strategy_selection rows from SQL source bars."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_DB_URL_FILE = Path("/root/secrets/openclaw/database-url")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+$")
METADATA_COLUMNS = (
    "run_id",
    "available_time",
    "target_candidate_id",
    "3_strategy_family",
    "3_strategy_variant",
    "variant_spec_ref",
    "signal_state",
    "exposure",
)


def _load_generator():
    return importlib.import_module("data_feature.feature_03_strategy_selection.generator")


def _load_psycopg():
    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except ModuleNotFoundError as error:  # pragma: no cover - environment guard
        raise SystemExit("psycopg is required for SQL generation; install psycopg[binary].") from error
    return psycopg, dict_row


def _database_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    value = os.environ.get("OPENCLAW_DATABASE_URL", "").strip()
    if value:
        return value
    if DEFAULT_DB_URL_FILE.exists():
        return DEFAULT_DB_URL_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit(f"database URL not supplied and {DEFAULT_DB_URL_FILE} does not exist")


def _quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"unsafe SQL identifier: {identifier!r}")
    return '"' + identifier.replace('"', '""') + '"'


def _qualified(schema: str, table: str) -> str:
    return f"{_quote_identifier(schema)}.{_quote_identifier(table)}"


def load_request(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("feature_03 request JSON must be an object")
    feature = payload.get("feature") or payload.get("source")
    if feature and feature != "feature_03_strategy_selection":
        raise ValueError("request feature/source must be feature_03_strategy_selection")
    return payload


def request_params(request: Mapping[str, Any]) -> dict[str, Any]:
    params = request.get("params") or {}
    if not isinstance(params, Mapping):
        raise ValueError("request params must be an object")
    return dict(params)


def fetch_source_bars(
    cursor: Any,
    *,
    source_schema: str,
    source_table: str,
    source_start: str | None = None,
    source_end: str | None = None,
    symbols: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if source_start:
        where.append("timestamp >= %s")
        params.append(source_start)
    if source_end:
        where.append("timestamp <= %s")
        params.append(source_end)
    if symbols:
        where.append("symbol = ANY(%s)")
        params.append([symbol.upper() for symbol in symbols])
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    cursor.execute(
        f"""
        SELECT
          symbol,
          timestamp,
          timestamp AS available_time,
          bar_open,
          bar_high,
          bar_low,
          bar_close,
          bar_volume
        FROM {_qualified(source_schema, source_table)}
        {where_sql}
        ORDER BY symbol ASC, timestamp ASC
        """,
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def write_feature_rows_sql(
    cursor: Any,
    rows: Sequence[Mapping[str, Any]],
    *,
    target_schema: str,
    target_table: str,
) -> None:
    if not rows:
        return

    for row in rows:
        for column in METADATA_COLUMNS:
            if column not in row:
                raise ValueError(f"feature_03 rows must include {column}")

    qualified_table = _qualified(target_schema, target_table)
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote_identifier(target_schema)}")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {qualified_table} (
          "run_id" TEXT NOT NULL,
          "available_time" TIMESTAMPTZ NOT NULL,
          "target_candidate_id" TEXT NOT NULL,
          "3_strategy_family" TEXT NOT NULL,
          "3_strategy_variant" TEXT NOT NULL,
          "variant_spec_ref" TEXT NOT NULL,
          "signal_state" TEXT NOT NULL,
          "exposure" DOUBLE PRECISION NOT NULL,
          "feature_payload_json" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          PRIMARY KEY ("run_id", "available_time", "target_candidate_id", "3_strategy_family", "3_strategy_variant")
        )
        """
    )

    insert_sql = f"""
        INSERT INTO {qualified_table} ({", ".join(_quote_identifier(column) for column in METADATA_COLUMNS)}, "feature_payload_json")
        VALUES ({", ".join(["%s"] * (len(METADATA_COLUMNS) + 1))}::jsonb)
        ON CONFLICT ("run_id", "available_time", "target_candidate_id", "3_strategy_family", "3_strategy_variant") DO UPDATE SET
          "variant_spec_ref" = EXCLUDED."variant_spec_ref",
          "signal_state" = EXCLUDED."signal_state",
          "exposure" = EXCLUDED."exposure",
          "feature_payload_json" = EXCLUDED."feature_payload_json"
    """
    for row in rows:
        payload = {key: value for key, value in row.items() if key not in METADATA_COLUMNS}
        cursor.execute(insert_sql, [*[row.get(column) for column in METADATA_COLUMNS], json.dumps(payload, sort_keys=True, default=str)])


def _rows_from_request_or_file(request: Mapping[str, Any], params: Mapping[str, Any], key: str, explicit_path: Path | None) -> list[dict[str, Any]]:
    generator = _load_generator()
    if explicit_path is not None:
        return generator.read_json_rows(explicit_path)
    direct = params.get(key) or request.get(key)
    if isinstance(direct, list):
        return [dict(item) for item in direct]
    path_value = params.get(f"{key}_path") or request.get(f"{key}_path")
    if path_value:
        return generator.read_json_rows(Path(str(path_value)))
    return []


def _symbols_from_candidates(candidate_rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted({str(row.get("symbol") or row.get("routing_symbol") or "").strip().upper() for row in candidate_rows if str(row.get("symbol") or row.get("routing_symbol") or "").strip()})


def generate_sql(
    *,
    database_url: str,
    request_json: Path | None,
    candidate_json: Path | None,
    variant_json: Path | None,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    source_start: str | None,
    source_end: str | None,
    run_id: str | None,
) -> tuple[int, str, str]:
    generator = _load_generator()
    request = load_request(request_json)
    params = request_params(request)
    candidate_rows = _rows_from_request_or_file(request, params, "target_candidates", candidate_json)
    variant_rows = _rows_from_request_or_file(request, params, "strategy_variants", variant_json)
    if not candidate_rows:
        raise ValueError("target candidates are required via request params.target_candidates or --candidate-json")
    if not variant_rows:
        raise ValueError("strategy variants are required via request params.strategy_variants or --variant-json")
    effective_start = source_start or str(params.get("start") or "") or None
    effective_end = source_end or str(params.get("end") or "") or None
    effective_run_id = run_id or str(request.get("run_id") or params.get("run_id") or request.get("task_id") or "adhoc")
    symbols = _symbols_from_candidates(candidate_rows)

    effective_source_schema = str(params.get("source_schema") or source_schema)
    effective_source_table = str(params.get("source_table") or source_table)
    effective_target_schema = str(params.get("target_schema") or target_schema)
    effective_target_table = str(params.get("target_table") or target_table)

    psycopg, dict_row = _load_psycopg()
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            bar_rows = fetch_source_bars(
                cursor,
                source_schema=effective_source_schema,
                source_table=effective_source_table,
                source_start=effective_start,
                source_end=effective_end,
                symbols=symbols,
            )
            inputs = generator.build_inputs(bar_rows=bar_rows, candidate_rows=candidate_rows, variant_rows=variant_rows)
            rows = generator.generate_rows(inputs, run_id=effective_run_id)
            write_feature_rows_sql(cursor, rows, target_schema=effective_target_schema, target_table=effective_target_table)
            return len(rows), effective_target_schema, effective_target_table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="PostgreSQL URL. Defaults to OPENCLAW_DATABASE_URL or the local OpenClaw DB secret file.")
    parser.add_argument("--request-json", type=Path, help="Manager-issued feature_03 request JSON.")
    parser.add_argument("--candidate-json", type=Path, help="JSON list of target candidate rows when not embedded in the request.")
    parser.add_argument("--variant-json", type=Path, help="JSON list of reviewed strategy variant specs when not embedded in the request.")
    parser.add_argument("--source-schema", default="trading_data")
    parser.add_argument("--source-table", default="source_03_strategy_selection")
    parser.add_argument("--target-schema", default="trading_data")
    parser.add_argument("--target-table", default="feature_03_strategy_selection")
    parser.add_argument("--source-start", help="Optional lower timestamp bound for source bars. Defaults to request params.start.")
    parser.add_argument("--source-end", help="Optional upper timestamp bound for source bars. Defaults to request params.end.")
    parser.add_argument("--run-id", help="Simulation run id. Defaults to request run_id, params.run_id, task_id, or adhoc.")
    args = parser.parse_args(argv)

    row_count, effective_target_schema, effective_target_table = generate_sql(
        database_url=_database_url(args.database_url),
        request_json=args.request_json,
        candidate_json=args.candidate_json,
        variant_json=args.variant_json,
        source_schema=args.source_schema,
        source_table=args.source_table,
        target_schema=args.target_schema,
        target_table=args.target_table,
        source_start=args.source_start,
        source_end=args.source_end,
        run_id=args.run_id,
    )
    print(f"generated {row_count} rows into {effective_target_schema}.{effective_target_table}")
    return 0
