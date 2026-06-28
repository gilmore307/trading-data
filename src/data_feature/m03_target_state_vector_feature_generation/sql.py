"""SQL wrapper for m03_target_state_vector_feature_generation production.

Reads accepted ``m03_target_state_vector_data_acquisition`` rows plus optional point-in-time M01
and M02 context rows, runs the deterministic feature generator, and writes
``trading_data.model_03_target_state_vector_feature_generation`` with inspectable JSONB blocks.
"""
from __future__ import annotations

import argparse
import csv
import gc
import importlib
import json
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from itertools import chain
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from data_runtime.config import database_url_file

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
METADATA_COLUMNS = (
    "run_id",
    "source_run_ref",
    "available_time",
    "tradeable_time",
    "target_candidate_id",
    "market_context_state_ref",
    "sector_context_state_ref",
    "target_context_state_version",
)
JSONB_COLUMNS = (
    "market_state_features",
    "sector_state_features",
    "target_state_features",
    "cross_state_features",
    "feature_quality_diagnostics",
)
KEY_COLUMNS = ("target_candidate_id", "available_time", "target_context_state_version")
INSERT_BATCH_SIZE = 1000
SOURCE_LOOKBACK_ROWS = 10080
OPTION_CHAIN_LOOKBACK_DAYS = 35
DEFAULT_TARGET_CONTEXT_MAPPING_PATH = Path("/root/projects/trading-storage/main/shared/model_02_target_context_mapping.csv")
DEFAULT_OPTION_CHAIN_SOURCE_TABLE = "option_chain_state_source"
MAPPING_METHOD_RANK = {
    "crypto_business_context": 10,
    "primary_sector_context": 20,
    "secondary_sector_context": 30,
    "weak_demand_side_context": 90,
}
SOURCE_COLUMNS = (
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
)
OPTION_CHAIN_SOURCE_COLUMNS = (
    "underlying",
    "snapshot_time",
    "option_symbol",
    "expiration",
    "option_right_type",
    "strike",
    "bid",
    "ask",
    "mid",
    "spread_pct",
    "bid_size",
    "ask_size",
    "implied_vol",
    "delta",
    "underlying_price",
    "days_to_expiration",
    "bar_volume",
    "bar_trade_count",
    "trade_notional",
    "open_interest",
    "open_interest_change",
)


def _load_generator():
    return importlib.import_module("data_feature.m03_target_state_vector_feature_generation.generator")


def _load_psycopg():
    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except ModuleNotFoundError as error:  # pragma: no cover
        raise SystemExit("psycopg is required for SQL generation; install psycopg[binary].") from error
    return psycopg, dict_row


def _database_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    value = os.environ.get("OPENCLAW_DATABASE_URL", "").strip()
    if value:
        return value
    path = database_url_file()
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    raise SystemExit(f"database URL not supplied and {path} does not exist")


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_task_progress(
    *,
    processed_count: int | None = None,
    expected_count: int | None = None,
    node_id: str,
    node_label: str,
    extra: Mapping[str, Any] | None = None,
) -> None:
    """Refresh manager task progress when running under the stage executor."""

    progress_path_text = os.environ.get("TRADING_MANAGER_TASK_PROGRESS_PATH", "").strip()
    worker_id = os.environ.get("TRADING_MANAGER_TASK_PROGRESS_WORKER_ID", "").strip()
    task_uid = os.environ.get("TRADING_MANAGER_TASK_PROGRESS_TASK_UID", "").strip()
    stage_id = os.environ.get("TRADING_MANAGER_TASK_PROGRESS_STAGE_ID", "").strip()
    if not progress_path_text or not worker_id or not task_uid or not stage_id:
        return

    progress_path = Path(progress_path_text)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    now = _utc_now_iso()
    progress_extra = {"progress_basis": "feature partitions required by the six-month fold"}
    if extra:
        progress_extra.update(dict(extra))
    payload = {
        "contract_type": "manager_worker_task_progress",
        "worker_id": worker_id,
        "task_uid": task_uid,
        "stage_id": stage_id,
        "status": "running",
        "unit_label": "feature months",
        "processed_count": processed_count,
        "expected_count": expected_count,
        "elapsed_seconds": None,
        "expected_seconds": None,
        "updated_at_utc": now,
        "progress_source": "active_progress_file",
        "progress_basis": progress_extra["progress_basis"],
        "extra": progress_extra,
        "nodes": [
            {
                "node_id": node_id,
                "node_label": node_label,
                "status": "running",
                "processed_count": processed_count,
                "expected_count": expected_count,
                "elapsed_seconds": None,
                "expected_seconds": None,
                "updated_at_utc": now,
            }
        ],
    }
    tmp = progress_path.with_name(f".{progress_path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(progress_path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"unsafe SQL identifier: {identifier!r}")
    return '"' + identifier.replace('"', '""') + '"'


def _qualified(schema: str, table: str) -> str:
    return f"{_quote_identifier(schema)}.{_quote_identifier(table)}"


def _column_list(columns: Sequence[str], *, prefix: str | None = None) -> str:
    if prefix:
        return ", ".join(f"{prefix}.{_quote_identifier(column)}" for column in columns)
    return ", ".join(_quote_identifier(column) for column in columns)


def fetch_source_rows(
    cursor: Any,
    *,
    source_schema: str,
    source_table: str,
    source_start: str | None = None,
    source_end: str | None = None,
) -> list[dict[str, Any]]:
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
        SELECT {_column_list(SOURCE_COLUMNS)}
        FROM {_qualified(source_schema, source_table)}
        {where_sql}
        ORDER BY target_candidate_id ASC, available_time ASC, timestamp ASC
        """,
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def fetch_source_rows_with_lookback(
    cursor: Any,
    *,
    source_schema: str,
    source_table: str,
    history_start: str,
    output_start: str,
    output_end: str,
    lookback_rows: int = SOURCE_LOOKBACK_ROWS,
) -> list[dict[str, Any]]:
    columns_sql = _column_list(SOURCE_COLUMNS)
    qualified = _qualified(source_schema, source_table)
    cursor.execute(
        f"""
        WITH prior_rows AS (
          SELECT
            {columns_sql},
            row_number() OVER (
              PARTITION BY "target_candidate_id"
              ORDER BY "available_time" DESC, "timestamp" DESC
            ) AS history_rank
          FROM {qualified}
          WHERE "available_time" >= %s AND "available_time" < %s
        ),
        output_rows AS (
          SELECT {columns_sql}
          FROM {qualified}
          WHERE "available_time" >= %s AND "available_time" < %s
        )
        SELECT {_column_list(SOURCE_COLUMNS, prefix="combined")}
        FROM (
          SELECT {columns_sql} FROM prior_rows WHERE history_rank <= %s
          UNION ALL
          SELECT {columns_sql} FROM output_rows
        ) AS combined
        ORDER BY "target_candidate_id" ASC, "available_time" ASC, "timestamp" ASC
        """,
        [history_start, output_start, output_start, output_end, lookback_rows],
    )
    return [dict(row) for row in cursor.fetchall()]


def fetch_context_rows(
    cursor: Any,
    *,
    schema: str,
    table: str,
    ref_column: str,
    source_start: str | None = None,
    source_end: str | None = None,
    filter_column: str | None = None,
    filter_values: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(cursor, schema=schema, table=table):
        return []
    where: list[str] = []
    params: list[Any] = []
    if source_end:
        where.append("available_time < %s")
        params.append(source_end)
    normalized_filter_values = sorted({str(value).strip().upper() for value in filter_values or () if str(value).strip()})
    if filter_column and normalized_filter_values:
        where.append(f"UPPER({_quote_identifier(filter_column)}::text) = ANY(%s)")
        params.append(normalized_filter_values)
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    cursor.execute(
        f"""
        SELECT *
        FROM {_qualified(schema, table)}
        {where_sql}
        ORDER BY available_time ASC
        """,
        params,
    )
    rows = [dict(row) for row in cursor.fetchall()]
    for row in rows:
        row.setdefault("context_ref", row.get(ref_column) or row.get("model_run_id") or row.get("target_context_state_ref"))
    return rows


def table_exists(cursor: Any, *, schema: str, table: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_ref", [f"{schema}.{table}"])
    row = cursor.fetchone()
    if row is None:
        return False
    if isinstance(row, Mapping):
        return bool(row.get("table_ref"))
    return bool(row[0])


def fetch_option_chain_rows(
    cursor: Any,
    *,
    source_schema: str,
    source_table: str | None,
    source_start: str | None = None,
    source_end: str | None = None,
    underlyings: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    if not source_table or not table_exists(cursor, schema=source_schema, table=source_table):
        return []
    where: list[str] = []
    params: list[Any] = []
    if source_start:
        where.append("snapshot_time >= %s")
        params.append(source_start)
    if source_end:
        where.append("snapshot_time < %s")
        params.append(source_end)
    normalized_underlyings = sorted({str(value).strip().upper() for value in underlyings or () if str(value).strip()})
    if normalized_underlyings:
        where.append('UPPER("underlying"::text) = ANY(%s)')
        params.append(normalized_underlyings)
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    cursor.execute(
        f"""
        SELECT {", ".join(_quote_identifier(column) for column in OPTION_CHAIN_SOURCE_COLUMNS)}
        FROM {_qualified(source_schema, source_table)}
        {where_sql}
        ORDER BY underlying ASC, snapshot_time ASC, expiration ASC, option_right_type ASC, strike ASC, option_symbol ASC
        """,
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def load_accepted_target_context_mappings(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    mapping_path = Path(path)
    if not mapping_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with mapping_path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            if str(row.get("review_status") or "").strip() != "accepted":
                continue
            target_symbol = str(row.get("target_symbol") or "").strip().upper()
            layer2_context_symbol = str(row.get("layer2_context_symbol") or "").strip().upper()
            if not target_symbol or not layer2_context_symbol:
                continue
            method_type = str(row.get("layer2_mapping_method_type") or "").strip()
            rows.append(
                {
                    "target_symbol": target_symbol,
                    "target_asset_class": str(row.get("target_asset_class") or "").strip(),
                    "layer2_context_symbol": layer2_context_symbol,
                    "optionable_proxy_status": str(row.get("optionable_proxy_status") or "").strip(),
                    "mapping_rank": MAPPING_METHOD_RANK.get(method_type, 100),
                }
            )
    return sorted(rows, key=lambda row: (row["target_symbol"], row["mapping_rank"], row["layer2_context_symbol"]))


def fetch_candidate_rows(
    cursor: Any,
    *,
    source_schema: str,
    source_table: str,
    sector_context_schema: str,
    sector_context_table: str,
    source_start: str | None = None,
    source_end: str | None = None,
    target_context_mapping_path: str | Path | None = DEFAULT_TARGET_CONTEXT_MAPPING_PATH,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if source_start:
        where.append('s."available_time" >= %s')
        params.append(source_start)
    if source_end:
        where.append('s."available_time" < %s')
        params.append(source_end)
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    mapping_rows = load_accepted_target_context_mappings(target_context_mapping_path)
    sector_table_exists = table_exists(cursor, schema=sector_context_schema, table=sector_context_table)
    mapping_cte = ""
    mapping_join = ""
    mapping_select = "NULL::text"
    mapping_asset_class_select = "NULL::text"
    mapping_option_status_select = "NULL::text"
    mapping_params: list[Any] = []
    if mapping_rows:
        value_sql = ", ".join(["(%s, %s, %s, %s, %s)"] * len(mapping_rows))
        mapping_cte = f"""
        WITH target_context_mapping(target_symbol, layer2_context_symbol, mapping_rank, target_asset_class, optionable_proxy_status) AS (
          VALUES {value_sql}
        )
        """
        for row in mapping_rows:
            mapping_params.extend([
                row["target_symbol"],
                row["layer2_context_symbol"],
                row["mapping_rank"],
                row["target_asset_class"],
                row["optionable_proxy_status"],
            ])
        mapping_join = """
        LEFT JOIN LATERAL (
          SELECT m.layer2_context_symbol, m.target_asset_class, m.optionable_proxy_status
          FROM target_context_mapping AS m
          WHERE m.target_symbol = s."symbol"
          ORDER BY m.mapping_rank ASC, m.layer2_context_symbol ASC
          LIMIT 1
        ) AS mapping_l2 ON TRUE
        """
        mapping_select = "mapping_l2.layer2_context_symbol"
        mapping_asset_class_select = "mapping_l2.target_asset_class"
        mapping_option_status_select = "mapping_l2.optionable_proxy_status"
    direct_l2_join = ""
    direct_l2_select = "NULL::text"
    if sector_table_exists:
        direct_l2_join = f"""
        LEFT JOIN LATERAL (
          SELECT l2."sector_or_industry_symbol"
          FROM {_qualified(sector_context_schema, sector_context_table)} AS l2
          WHERE l2."sector_or_industry_symbol" = s."symbol"
          LIMIT 1
        ) AS direct_l2 ON TRUE
        """
        direct_l2_select = "direct_l2.\"sector_or_industry_symbol\""
    cursor.execute(
        f"""
        {mapping_cte}
        SELECT DISTINCT
          s."target_candidate_id",
          s."symbol",
          COALESCE({direct_l2_select}, {mapping_select}) AS "sector_context_symbol",
          {mapping_asset_class_select} AS "target_asset_class",
          {mapping_option_status_select} AS "optionable_underlying_status"
        FROM {_qualified(source_schema, source_table)} AS s
        {direct_l2_join}
        {mapping_join}
        {where_sql}
        ORDER BY s."target_candidate_id" ASC, s."symbol" ASC
        """,
        [*mapping_params, *params],
    )
    return [dict(row) for row in cursor.fetchall()]


def write_feature_rows_sql(
    cursor: Any,
    rows: Iterable[Mapping[str, Any]],
    *,
    target_schema: str,
    target_table: str,
) -> int:
    row_iterator = iter(rows)
    first_row = next(row_iterator, None)
    if first_row is None:
        return 0

    qualified_table = _qualified(target_schema, target_table)
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote_identifier(target_schema)}")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {qualified_table} (
          "run_id" TEXT NOT NULL,
          "source_run_ref" TEXT NOT NULL,
          "available_time" TIMESTAMPTZ NOT NULL,
          "tradeable_time" TIMESTAMPTZ NOT NULL,
          "target_candidate_id" TEXT NOT NULL,
          "market_context_state_ref" TEXT,
          "sector_context_state_ref" TEXT,
          "target_context_state_version" TEXT NOT NULL,
          "market_state_features" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          "sector_state_features" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          "target_state_features" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          "cross_state_features" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          "feature_quality_diagnostics" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          PRIMARY KEY ("target_candidate_id", "available_time", "target_context_state_version")
        )
        """
    )
    columns = (*METADATA_COLUMNS, *JSONB_COLUMNS)
    placeholders = ["%s"] * len(METADATA_COLUMNS) + ["%s::jsonb"] * len(JSONB_COLUMNS)
    update_columns = [column for column in columns if column not in KEY_COLUMNS]
    insert_sql = f"""
        INSERT INTO {qualified_table} ({", ".join(_quote_identifier(column) for column in columns)})
        VALUES ({", ".join(placeholders)})
        ON CONFLICT ({", ".join(_quote_identifier(column) for column in KEY_COLUMNS)}) DO UPDATE SET
          {", ".join(f'{_quote_identifier(column)} = EXCLUDED.{_quote_identifier(column)}' for column in update_columns)}
    """
    batch: list[list[Any]] = []
    connection = getattr(cursor, "connection", None)
    row_count = 0
    for row in chain((first_row,), row_iterator):
        for column in (*METADATA_COLUMNS, *JSONB_COLUMNS):
            if column not in row:
                raise ValueError(f"feature_03 rows must include {column}")
        values = [row.get(column) for column in METADATA_COLUMNS]
        values.extend(json.dumps(row.get(column) or {}, sort_keys=True, default=str) for column in JSONB_COLUMNS)
        batch.append(values)
        row_count += 1
        if len(batch) >= INSERT_BATCH_SIZE:
            cursor.executemany(insert_sql, batch)
            batch.clear()
            if connection is not None:
                connection.commit()
            gc.collect()
    if batch:
        cursor.executemany(insert_sql, batch)
        if connection is not None:
            connection.commit()
    return row_count


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _bounded_time_slices(source_start: str | None, source_end: str | None, *, days: int = 7) -> list[tuple[str, str]]:
    if not source_start or not source_end:
        return []
    start = _parse_datetime(source_start)
    end = _parse_datetime(source_end)
    slices: list[tuple[str, str]] = []
    cursor = start
    while cursor < end:
        next_cursor = min(cursor + timedelta(days=days), end)
        slices.append((_iso(cursor), _iso(next_cursor)))
        cursor = next_cursor
    return slices


def _row_in_window(row: Mapping[str, Any], *, window_start: str, window_end: str) -> bool:
    available_time = _parse_datetime(str(row.get("available_time")))
    return _parse_datetime(window_start) <= available_time < _parse_datetime(window_end)


def generate_sql(
    *,
    database_url: str,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    source_start: str | None,
    source_end: str | None,
    market_context_schema: str,
    market_context_table: str,
    sector_context_schema: str,
    sector_context_table: str,
    target_context_mapping_path: str | Path | None,
    option_chain_source_schema: str,
    option_chain_source_table: str | None,
    run_id: str,
    target_context_state_version: str,
) -> int:
    generator = _load_generator()
    psycopg, dict_row = _load_psycopg()
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            slices = _bounded_time_slices(source_start, source_end)
            expected_count = len(slices) if slices else 1
            _write_task_progress(
                processed_count=0,
                expected_count=expected_count,
                node_id="feature_generation_prepare",
                node_label="Preparing feature generation inputs",
            )
            candidate_rows = fetch_candidate_rows(
                cursor,
                source_schema=source_schema,
                source_table=source_table,
                sector_context_schema=sector_context_schema,
                sector_context_table=sector_context_table,
                source_start=source_start,
                source_end=source_end,
                target_context_mapping_path=target_context_mapping_path,
            )
            _write_task_progress(
                processed_count=0,
                expected_count=expected_count,
                node_id="feature_generation_candidates_loaded",
                node_label="Loaded target candidate universe",
                extra={"candidate_count": len(candidate_rows)},
            )
            candidate_symbols = sorted({str(row.get("symbol") or "").strip().upper() for row in candidate_rows if str(row.get("symbol") or "").strip()})
            sector_context_symbols = sorted({
                str(row.get("sector_context_symbol") or "").strip().upper()
                for row in candidate_rows
                if str(row.get("sector_context_symbol") or "").strip()
            })
            market_rows = fetch_context_rows(cursor, schema=market_context_schema, table=market_context_table, ref_column="market_context_state_ref", source_start=source_start, source_end=source_end)
            sector_rows = fetch_context_rows(
                cursor,
                schema=sector_context_schema,
                table=sector_context_table,
                ref_column="sector_context_state_ref",
                source_start=source_start,
                source_end=source_end,
                filter_column="sector_or_industry_symbol",
                filter_values=sector_context_symbols,
            )
            _write_task_progress(
                processed_count=0,
                expected_count=expected_count,
                node_id="feature_generation_context_loaded",
                node_label="Loaded market and sector context",
                extra={
                    "candidate_count": len(candidate_rows),
                    "market_context_row_count": len(market_rows),
                    "sector_context_row_count": len(sector_rows),
                },
            )
            if not slices:
                source_rows = fetch_source_rows(cursor, source_schema=source_schema, source_table=source_table, source_start=source_start, source_end=source_end)
                option_chain_rows = fetch_option_chain_rows(
                    cursor,
                    source_schema=option_chain_source_schema,
                    source_table=option_chain_source_table,
                    source_start=source_start,
                    source_end=source_end,
                    underlyings=candidate_symbols,
                )
                inputs = generator.build_inputs(bar_rows=source_rows, candidate_rows=candidate_rows, market_context_rows=market_rows, sector_context_rows=sector_rows, option_chain_rows=option_chain_rows)
                rows = generator.iter_rows(inputs, run_id=run_id, target_context_state_version=target_context_state_version)
                row_count = write_feature_rows_sql(cursor, rows, target_schema=target_schema, target_table=target_table)
                _write_task_progress(
                    processed_count=1,
                    expected_count=1,
                    node_id="feature_generation_window_completed",
                    node_label="Completed feature generation window",
                    extra={"rows_written": row_count},
                )
                return row_count

            total_rows = 0
            history_start = source_start or slices[0][0]
            history_floor = _parse_datetime(history_start)
            sample_targets = candidate_symbols[:6]
            for index, (window_start, window_end) in enumerate(slices, start=1):
                _write_task_progress(
                    processed_count=index - 1,
                    expected_count=len(slices),
                    node_id="feature_generation_window_started",
                    node_label=f"Generating feature window {index} of {len(slices)}",
                    extra={
                        "window_start": window_start,
                        "window_end": window_end,
                        "rows_written": total_rows,
                        "candidate_symbol_count": len(candidate_symbols),
                        "sample_targets": sample_targets,
                    },
                )
                source_rows = fetch_source_rows_with_lookback(
                    cursor,
                    source_schema=source_schema,
                    source_table=source_table,
                    history_start=history_start,
                    output_start=window_start,
                    output_end=window_end,
                )
                option_start = _iso(max(history_floor, _parse_datetime(window_start) - timedelta(days=OPTION_CHAIN_LOOKBACK_DAYS)))
                option_chain_rows = fetch_option_chain_rows(
                    cursor,
                    source_schema=option_chain_source_schema,
                    source_table=option_chain_source_table,
                    source_start=option_start,
                    source_end=window_end,
                    underlyings=candidate_symbols,
                )
                inputs = generator.build_inputs(bar_rows=source_rows, candidate_rows=candidate_rows, market_context_rows=market_rows, sector_context_rows=sector_rows, option_chain_rows=option_chain_rows)
                rows = generator.iter_rows(
                    inputs,
                    run_id=run_id,
                    target_context_state_version=target_context_state_version,
                    emit_start_time=_parse_datetime(window_start),
                    emit_end_time=_parse_datetime(window_end),
                )
                window_rows = write_feature_rows_sql(cursor, rows, target_schema=target_schema, target_table=target_table)
                total_rows += window_rows
                _write_task_progress(
                    processed_count=index,
                    expected_count=len(slices),
                    node_id="feature_generation_window_completed",
                    node_label=f"Completed feature window {index} of {len(slices)}",
                    extra={
                        "window_start": window_start,
                        "window_end": window_end,
                        "window_row_count": window_rows,
                        "rows_written": total_rows,
                        "candidate_symbol_count": len(candidate_symbols),
                        "sample_targets": sample_targets,
                    },
                )
                gc.collect()
            return total_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="PostgreSQL URL. Defaults to OPENCLAW_DATABASE_URL or local OpenClaw DB secret file.")
    parser.add_argument("--source-schema", default="trading_data")
    parser.add_argument("--source-table", default="model_03_target_state_vector_data_acquisition")
    parser.add_argument("--target-schema", default="trading_data")
    parser.add_argument("--target-table", default="model_03_target_state_vector_feature_generation")
    parser.add_argument("--market-context-schema", default="trading_model")
    parser.add_argument("--market-context-table", default="model_01_market_regime_model_generation")
    parser.add_argument("--sector-context-schema", default="trading_model")
    parser.add_argument("--sector-context-table", default="model_02_sector_context_model_generation")
    parser.add_argument("--option-chain-source-schema", default="trading_data")
    parser.add_argument("--option-chain-source-table", default=DEFAULT_OPTION_CHAIN_SOURCE_TABLE)
    parser.add_argument("--target-context-mapping-path", type=Path, default=DEFAULT_TARGET_CONTEXT_MAPPING_PATH)
    parser.add_argument("--source-start")
    parser.add_argument("--source-end")
    parser.add_argument("--run-id", default="model_03_target_state_vector_feature_generation_sql")
    parser.add_argument(
        "--target-context-state-version",
        dest="target_context_state_version",
        default="target_context_state",
        help="M02 target context state contract version.",
    )
    args = parser.parse_args(argv)
    row_count = generate_sql(
        database_url=_database_url(args.database_url),
        source_schema=args.source_schema,
        source_table=args.source_table,
        target_schema=args.target_schema,
        target_table=args.target_table,
        source_start=args.source_start,
        source_end=args.source_end,
        market_context_schema=args.market_context_schema,
        market_context_table=args.market_context_table,
        sector_context_schema=args.sector_context_schema,
        sector_context_table=args.sector_context_table,
        target_context_mapping_path=args.target_context_mapping_path,
        option_chain_source_schema=args.option_chain_source_schema,
        option_chain_source_table=args.option_chain_source_table,
        run_id=args.run_id,
        target_context_state_version=args.target_context_state_version,
    )
    print(f"generated {row_count} rows into {args.target_schema}.{args.target_table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
