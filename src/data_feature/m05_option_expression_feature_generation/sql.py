"""SQL wrapper for m05_option_expression_feature_generation production."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from data_runtime.config import database_url_file

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COLUMNS = (
    "run_id",
    "source_run_ref",
    "underlying",
    "snapshot_time",
    "snapshot_type",
    "option_symbol",
    "feature_payload_json",
    "feature_quality_diagnostics",
)
KEY_COLUMNS = ("underlying", "snapshot_time", "snapshot_type", "option_symbol")
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
        where.append("snapshot_time >= %s")
        params.append(source_start)
    if source_end:
        where.append("snapshot_time < %s")
        params.append(source_end)
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    snapshot_type_expr = "'source_cache'::text" if source_table == "option_chain_state_source" else "snapshot_type::text"
    cursor.execute(
        f"""
        SELECT underlying,
               snapshot_time,
               {snapshot_type_expr} AS snapshot_type,
               option_symbol, expiration, option_right_type, strike,
               bid, ask, mid, spread, spread_pct, bid_size, ask_size, implied_vol, delta, theta, vega, rho,
               underlying_price, underlying_timestamp, days_to_expiration
        FROM {_qualified(source_schema, source_table)}
        {where_sql}
        ORDER BY underlying ASC, snapshot_time ASC, snapshot_type ASC, option_symbol ASC
        """,
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def insert_feature_rows_from_source_sql(
    cursor: Any,
    *,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    source_start: str | None,
    source_end: str | None,
    run_id: str,
) -> int:
    qualified_source = _qualified(source_schema, source_table)
    qualified_target = _qualified(target_schema, target_table)
    source_run_ref_expr = "source_run_ref" if source_table == "option_chain_state_source" else "'option_chain_state_source'::text"
    snapshot_type_expr = "'source_cache'::text" if source_table == "option_chain_state_source" else "snapshot_type::text"
    where: list[str] = ["underlying IS NOT NULL", "snapshot_time IS NOT NULL", "option_symbol IS NOT NULL"]
    params: list[Any] = []
    if source_table != "option_chain_state_source":
        where.append("snapshot_type IS NOT NULL")
    if source_start:
        where.append("snapshot_time >= %s")
        params.append(source_start)
    if source_end:
        where.append("snapshot_time < %s")
        params.append(source_end)
    where_sql = " AND ".join(where)
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote(target_schema)}")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {qualified_target} (
          "run_id" TEXT NOT NULL,
          "source_run_ref" TEXT NOT NULL,
          "underlying" TEXT NOT NULL,
          "snapshot_time" TIMESTAMPTZ NOT NULL,
          "snapshot_type" TEXT NOT NULL,
          "option_symbol" TEXT NOT NULL,
          "feature_payload_json" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          "feature_quality_diagnostics" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          PRIMARY KEY ("underlying", "snapshot_time", "snapshot_type", "option_symbol")
        )
        """
    )
    cursor.execute(
        f"""
        WITH source_rows AS (
          SELECT
            underlying,
            snapshot_time,
            {snapshot_type_expr} AS snapshot_type,
            option_symbol,
            expiration,
            option_right_type,
            strike,
            bid,
            ask,
            COALESCE(mid, CASE WHEN bid IS NOT NULL AND ask IS NOT NULL THEN (bid + ask) / 2.0 ELSE NULL END) AS feature_mid,
            COALESCE(spread, CASE WHEN bid IS NOT NULL AND ask IS NOT NULL THEN ask - bid ELSE NULL END) AS feature_spread,
            spread_pct,
            bid_size,
            ask_size,
            implied_vol,
            delta,
            theta,
            vega,
            rho,
            underlying_price,
            days_to_expiration,
            COALESCE({source_run_ref_expr}, 'option_chain_state_source') AS source_run_ref
          FROM {qualified_source}
          WHERE {where_sql}
        ),
        feature_rows AS (
          SELECT
            %s AS run_id,
            source_run_ref,
            underlying::text AS underlying,
            snapshot_time,
            snapshot_type::text AS snapshot_type,
            option_symbol::text AS option_symbol,
            jsonb_build_object(
              'option_right_type', option_right_type,
              'days_to_expiration', days_to_expiration,
              'strike', strike,
              'underlying_price', underlying_price,
              'moneyness',
                CASE
                  WHEN strike IS NULL OR strike = 0 OR underlying_price IS NULL THEN NULL
                  WHEN lower(COALESCE(option_right_type, '')) = 'put' THEN (strike / underlying_price) - 1.0
                  ELSE (underlying_price / strike) - 1.0
                END,
              'bid', bid,
              'ask', ask,
              'mid', feature_mid,
              'spread', feature_spread,
              'spread_pct_mid', COALESCE(spread_pct, CASE WHEN feature_spread IS NOT NULL AND feature_mid IS NOT NULL AND feature_mid <> 0 THEN feature_spread / feature_mid ELSE NULL END),
              'bid_size', bid_size,
              'ask_size', ask_size,
              'quote_size_balance',
                CASE
                  WHEN bid_size IS NULL OR ask_size IS NULL OR (bid_size + ask_size) = 0 THEN NULL
                  ELSE (bid_size - ask_size) / (bid_size + ask_size)
                END,
              'implied_vol', implied_vol,
              'delta', delta,
              'theta', theta,
              'vega', vega,
              'rho', rho
            ) AS feature_payload_json,
            jsonb_build_object(
              'missing_required_fields',
                to_jsonb(ARRAY_REMOVE(ARRAY[
                  CASE WHEN underlying IS NULL OR underlying = '' THEN 'underlying' END,
                  CASE WHEN snapshot_time IS NULL THEN 'snapshot_time' END,
                  CASE WHEN snapshot_type IS NULL OR snapshot_type = '' THEN 'snapshot_type' END,
                  CASE WHEN option_symbol IS NULL OR option_symbol = '' THEN 'option_symbol' END,
                  CASE WHEN expiration IS NULL THEN 'expiration' END,
                  CASE WHEN option_right_type IS NULL OR option_right_type = '' THEN 'option_right_type' END,
                  CASE WHEN strike IS NULL OR strike = 0 THEN 'strike' END
                ], NULL)),
              'has_required_fields',
                underlying IS NOT NULL AND underlying <> ''
                AND snapshot_time IS NOT NULL
                AND snapshot_type IS NOT NULL AND snapshot_type <> ''
                AND option_symbol IS NOT NULL AND option_symbol <> ''
                AND expiration IS NOT NULL
                AND option_right_type IS NOT NULL AND option_right_type <> ''
                AND strike IS NOT NULL AND strike <> 0,
              'has_quote', bid IS NOT NULL OR ask IS NOT NULL OR feature_mid IS NOT NULL,
              'has_iv', implied_vol IS NOT NULL,
              'has_first_order_greeks', delta IS NOT NULL OR theta IS NOT NULL OR vega IS NOT NULL OR rho IS NOT NULL,
              'point_in_time_clock', 'snapshot_time',
              'source_table', 'option_chain_state_source'
            ) AS feature_quality_diagnostics
          FROM source_rows
        )
        INSERT INTO {qualified_target} ({", ".join(_quote(column) for column in COLUMNS)})
        SELECT {", ".join(_quote(column) for column in COLUMNS)}
        FROM feature_rows
        ON CONFLICT ({", ".join(_quote(column) for column in KEY_COLUMNS)}) DO UPDATE SET
          {", ".join(f'{_quote(column)} = EXCLUDED.{_quote(column)}' for column in COLUMNS if column not in KEY_COLUMNS)}
        """,
        [*params, run_id],
    )
    return int(getattr(cursor, "rowcount", 0) or 0)


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
          "underlying" TEXT NOT NULL,
          "snapshot_time" TIMESTAMPTZ NOT NULL,
          "snapshot_type" TEXT NOT NULL,
          "option_symbol" TEXT NOT NULL,
          "feature_payload_json" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          "feature_quality_diagnostics" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          PRIMARY KEY ("underlying", "snapshot_time", "snapshot_type", "option_symbol")
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
            return insert_feature_rows_from_source_sql(
                cursor,
                source_schema=source_schema,
                source_table=source_table,
                target_schema=target_schema,
                target_table=target_table,
                source_start=source_start,
                source_end=source_end,
                run_id=run_id,
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url")
    parser.add_argument("--source-schema", default="trading_data")
    parser.add_argument("--source-table", default="option_chain_state_source")
    parser.add_argument("--target-schema", default="trading_data")
    parser.add_argument("--target-table", default="m05_option_expression_feature_generation")
    parser.add_argument("--source-start")
    parser.add_argument("--source-end")
    parser.add_argument("--run-id", default="m05_option_expression_feature_generation_sql")
    args = parser.parse_args(argv)
    count = generate_sql(database_url=_database_url(args.database_url), source_schema=args.source_schema, source_table=args.source_table, target_schema=args.target_schema, target_table=args.target_table, source_start=args.source_start, source_end=args.source_end, run_id=args.run_id)
    print(f"generated {count} rows into {args.target_schema}.{args.target_table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
