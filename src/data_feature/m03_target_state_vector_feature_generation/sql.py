"""SQL wrapper for m03_target_state_vector_feature_generation production.

Reads accepted ``m03_target_state_vector_data_acquisition`` rows plus optional point-in-time Layer 1
and Layer 2 context rows, runs the deterministic feature generator, and writes
``trading_data.m03_target_state_vector_feature_generation`` with inspectable JSONB blocks.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

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
DEFAULT_TARGET_CONTEXT_MAPPING_PATH = Path("/root/projects/trading-storage/main/shared/layer_02_target_context_mapping.csv")
MAPPING_METHOD_RANK = {
    "crypto_business_context": 10,
    "primary_sector_context": 20,
    "secondary_sector_context": 30,
    "weak_demand_side_context": 90,
}


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


def _quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"unsafe SQL identifier: {identifier!r}")
    return '"' + identifier.replace('"', '""') + '"'


def _qualified(schema: str, table: str) -> str:
    return f"{_quote_identifier(schema)}.{_quote_identifier(table)}"


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
        SELECT
          target_candidate_id,
          symbol,
          timeframe,
          timestamp,
          available_time,
          bar_open,
          bar_high,
          bar_low,
          bar_close,
          bar_volume,
          bar_vwap,
          bar_trade_count,
          dollar_volume,
          quote_count,
          avg_bid,
          avg_ask,
          avg_bid_size,
          avg_ask_size,
          avg_spread,
          spread_bps,
          last_bid,
          last_ask
        FROM {_qualified(source_schema, source_table)}
        {where_sql}
        ORDER BY target_candidate_id ASC, available_time ASC, timestamp ASC
        """,
        params,
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
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if source_end:
        where.append("available_time < %s")
        params.append(source_end)
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
                    "layer2_context_symbol": layer2_context_symbol,
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
    holdings_schema: str,
    holdings_table: str,
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
    holdings_table_ref = f"{holdings_schema}.{holdings_table}"
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (holdings_table_ref,))
    exists = cursor.fetchone()
    if isinstance(exists, Mapping):
        holdings_exists = exists.get("table_ref") is not None
    else:
        holdings_exists = bool(exists and exists[0] is not None)
    holdings_join = ""
    holdings_select = "NULL::text"
    if holdings_exists:
        holdings_join = f"""
        LEFT JOIN LATERAL (
          SELECT h."etf_symbol"
          FROM {_qualified(holdings_schema, holdings_table)} AS h
          WHERE h."holding_symbol" = s."symbol"
            AND h."available_time" <= s."available_time"
          ORDER BY h."available_time" DESC, h."weight" DESC NULLS LAST, h."etf_symbol" ASC
          LIMIT 1
        ) AS h ON TRUE
        """
        holdings_select = 'h."etf_symbol"'
    mapping_rows = load_accepted_target_context_mappings(target_context_mapping_path)
    mapping_cte = ""
    mapping_join = ""
    mapping_select = "NULL::text"
    mapping_params: list[Any] = []
    if mapping_rows:
        value_sql = ", ".join(["(%s, %s, %s)"] * len(mapping_rows))
        mapping_cte = f"""
        WITH target_context_mapping(target_symbol, layer2_context_symbol, mapping_rank) AS (
          VALUES {value_sql}
        )
        """
        for row in mapping_rows:
            mapping_params.extend([row["target_symbol"], row["layer2_context_symbol"], row["mapping_rank"]])
        mapping_join = """
        LEFT JOIN LATERAL (
          SELECT m.layer2_context_symbol
          FROM target_context_mapping AS m
          WHERE m.target_symbol = s."symbol"
          ORDER BY m.mapping_rank ASC, m.layer2_context_symbol ASC
          LIMIT 1
        ) AS mapping_l2 ON TRUE
        """
        mapping_select = "mapping_l2.layer2_context_symbol"
    cursor.execute(
        f"""
        {mapping_cte}
        SELECT DISTINCT
          s."target_candidate_id",
          s."symbol",
          COALESCE(direct_l2."sector_or_industry_symbol", {mapping_select}, {holdings_select}) AS "sector_context_symbol"
        FROM {_qualified(source_schema, source_table)} AS s
        LEFT JOIN LATERAL (
          SELECT l2."sector_or_industry_symbol"
          FROM {_qualified(sector_context_schema, sector_context_table)} AS l2
          WHERE l2."sector_or_industry_symbol" = s."symbol"
          LIMIT 1
        ) AS direct_l2 ON TRUE
        {mapping_join}
        {holdings_join}
        {where_sql}
        ORDER BY s."target_candidate_id" ASC, s."symbol" ASC
        """,
        [*mapping_params, *params],
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
        for column in (*METADATA_COLUMNS, *JSONB_COLUMNS):
            if column not in row:
                raise ValueError(f"feature_03 rows must include {column}")

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
    for row in rows:
        values = [row.get(column) for column in METADATA_COLUMNS]
        values.extend(json.dumps(row.get(column) or {}, sort_keys=True, default=str) for column in JSONB_COLUMNS)
        batch.append(values)
        if len(batch) >= INSERT_BATCH_SIZE:
            cursor.executemany(insert_sql, batch)
            batch.clear()
    if batch:
        cursor.executemany(insert_sql, batch)


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
    holdings_schema: str,
    holdings_table: str,
    target_context_mapping_path: str | Path | None,
    run_id: str,
    target_context_state_version: str,
) -> int:
    generator = _load_generator()
    psycopg, dict_row = _load_psycopg()
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            source_rows = fetch_source_rows(cursor, source_schema=source_schema, source_table=source_table, source_start=source_start, source_end=source_end)
            market_rows = fetch_context_rows(cursor, schema=market_context_schema, table=market_context_table, ref_column="market_context_state_ref", source_start=source_start, source_end=source_end)
            sector_rows = fetch_context_rows(cursor, schema=sector_context_schema, table=sector_context_table, ref_column="sector_context_state_ref", source_start=source_start, source_end=source_end)
            candidate_rows = fetch_candidate_rows(
                cursor,
                source_schema=source_schema,
                source_table=source_table,
                sector_context_schema=sector_context_schema,
                sector_context_table=sector_context_table,
                holdings_schema=holdings_schema,
                holdings_table=holdings_table,
                source_start=source_start,
                source_end=source_end,
                target_context_mapping_path=target_context_mapping_path,
            )
            inputs = generator.build_inputs(bar_rows=source_rows, candidate_rows=candidate_rows, market_context_rows=market_rows, sector_context_rows=sector_rows)
            rows = generator.generate_rows(inputs, run_id=run_id, target_context_state_version=target_context_state_version)
            write_feature_rows_sql(cursor, rows, target_schema=target_schema, target_table=target_table)
            return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="PostgreSQL URL. Defaults to OPENCLAW_DATABASE_URL or local OpenClaw DB secret file.")
    parser.add_argument("--source-schema", default="trading_data")
    parser.add_argument("--source-table", default="m03_target_state_vector_data_acquisition")
    parser.add_argument("--target-schema", default="trading_data")
    parser.add_argument("--target-table", default="m03_target_state_vector_feature_generation")
    parser.add_argument("--market-context-schema", default="trading_model")
    parser.add_argument("--market-context-table", default="m01_market_regime_model_generation")
    parser.add_argument("--sector-context-schema", default="trading_model")
    parser.add_argument("--sector-context-table", default="m02_sector_context_model_generation")
    parser.add_argument("--holdings-schema", default="trading_data")
    parser.add_argument("--holdings-table", default="m02_sector_context_data_acquisition")
    parser.add_argument("--target-context-mapping-path", type=Path, default=DEFAULT_TARGET_CONTEXT_MAPPING_PATH)
    parser.add_argument("--source-start")
    parser.add_argument("--source-end")
    parser.add_argument("--run-id", default="m03_target_state_vector_feature_generation_sql")
    parser.add_argument(
        "--target-context-state-version",
        dest="target_context_state_version",
        default="target_context_state",
        help="Layer 3 target context state contract version.",
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
        holdings_schema=args.holdings_schema,
        holdings_table=args.holdings_table,
        target_context_mapping_path=args.target_context_mapping_path,
        run_id=args.run_id,
        target_context_state_version=args.target_context_state_version,
    )
    print(f"generated {row_count} rows into {args.target_schema}.{args.target_table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
