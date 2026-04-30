"""Generate feature_01_market_regime rows from SQL source bars into SQL storage."""
from __future__ import annotations

import argparse
import importlib
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_DB_URL_FILE = Path("/root/secrets/openclaw/database-url")
DEFAULT_UNIVERSE_CSV = Path("/root/projects/trading-storage/main/shared/market_regime_etf_universe.csv")
DEFAULT_COMBINATIONS_CSV = Path("/root/projects/trading-storage/main/shared/market_regime_relative_strength_combinations.csv")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_generator():
    return importlib.import_module("data_feature.feature_01_market_regime.generator")


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


def fetch_source_bars(
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
        where.append("timestamp >= %s")
        params.append(source_start)
    if source_end:
        where.append("timestamp <= %s")
        params.append(source_end)
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    cursor.execute(
        f"""
        SELECT
          symbol,
          timeframe,
          timestamp,
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

    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    if "snapshot_time" not in columns:
        raise ValueError("feature rows must include snapshot_time")

    qualified_table = _qualified(target_schema, target_table)
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote_identifier(target_schema)}")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {qualified_table} (
          "snapshot_time" TIMESTAMPTZ PRIMARY KEY
        )
        """
    )

    for column in columns:
        if column == "snapshot_time":
            continue
        cursor.execute(
            f"ALTER TABLE {qualified_table} ADD COLUMN IF NOT EXISTS {_quote_identifier(column)} DOUBLE PRECISION"
        )

    quoted_columns = [_quote_identifier(column) for column in columns]
    placeholders = ", ".join(["%s"] * len(columns))
    update_columns = [column for column in columns if column != "snapshot_time"]
    update_sql = ", ".join(
        f"{_quote_identifier(column)} = EXCLUDED.{_quote_identifier(column)}" for column in update_columns
    )
    conflict_sql = f"DO UPDATE SET {update_sql}" if update_sql else "DO NOTHING"
    insert_sql = f"""
        INSERT INTO {qualified_table} ({", ".join(quoted_columns)})
        VALUES ({placeholders})
        ON CONFLICT ("snapshot_time") {conflict_sql}
    """
    for row in rows:
        cursor.execute(insert_sql, [row.get(column) for column in columns])


def generate_sql(
    *,
    database_url: str,
    universe_csv: Path,
    combinations_csv: Path,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    source_start: str | None,
    source_end: str | None,
    snapshot_times: Sequence[str] | None,
) -> int:
    generator = _load_generator()
    psycopg, dict_row = _load_psycopg()
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            bar_rows = fetch_source_bars(
                cursor,
                source_schema=source_schema,
                source_table=source_table,
                source_start=source_start,
                source_end=source_end,
            )
            inputs = generator.build_inputs(
                bar_rows=bar_rows,
                universe_rows=generator.read_csv_rows(universe_csv),
                combination_rows=generator.read_csv_rows(combinations_csv),
            )
            rows = generator.generate_rows(inputs, snapshot_times=snapshot_times)
            write_feature_rows_sql(cursor, rows, target_schema=target_schema, target_table=target_table)
            return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="PostgreSQL URL. Defaults to OPENCLAW_DATABASE_URL or the local OpenClaw DB secret file.")
    parser.add_argument("--source-schema", default="trading_data")
    parser.add_argument("--source-table", default="source_01_market_regime")
    parser.add_argument("--target-schema", default="trading_data")
    parser.add_argument("--target-table", default="feature_01_market_regime")
    parser.add_argument("--source-start", help="Optional lower timestamp bound for source bars. Include enough lookback for requested features.")
    parser.add_argument("--source-end", help="Optional upper timestamp bound for source bars.")
    parser.add_argument("--universe-csv", type=Path, default=DEFAULT_UNIVERSE_CSV)
    parser.add_argument("--combinations-csv", type=Path, default=DEFAULT_COMBINATIONS_CSV)
    parser.add_argument("--snapshot-time", action="append", help="Optional ISO snapshot time. Repeat for multiple snapshots. Defaults to SPY 30-minute source-bar timestamps.")
    args = parser.parse_args(argv)

    row_count = generate_sql(
        database_url=_database_url(args.database_url),
        universe_csv=args.universe_csv,
        combinations_csv=args.combinations_csv,
        source_schema=args.source_schema,
        source_table=args.source_table,
        target_schema=args.target_schema,
        target_table=args.target_table,
        source_start=args.source_start,
        source_end=args.source_end,
        snapshot_times=args.snapshot_time,
    )
    print(f"generated {row_count} rows into {args.target_schema}.{args.target_table}")
    return 0


