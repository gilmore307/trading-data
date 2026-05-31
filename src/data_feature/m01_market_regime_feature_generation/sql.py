"""Generate m01_market_regime_feature_generation rows from SQL source bars into SQL storage."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

from data_runtime.config import database_url_file, shared_path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

DEFAULT_UNIVERSE_CSV = shared_path("main", "shared", "layer_01_02_market_context_etf_universe.csv")
DEFAULT_COMBINATIONS_CSV = shared_path("main", "shared", "layer_01_02_market_context_relative_strength_combinations.csv")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_generator():
    return importlib.import_module("data_feature.m01_market_regime_feature_generation.generator")


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


def fetch_source_bars(
    cursor: Any,
    *,
    source_schema: str,
    source_table: str,
    source_start: str | None = None,
    source_end: str | None = None,
) -> list[dict[str, Any]]:
    where: list[str] = [
        """
        (
          lower(timeframe) IN ('1m', '1min', '1minute')
          AND (timestamp AT TIME ZONE 'America/New_York')::time BETWEEN TIME '09:30' AND TIME '16:00'
          AND EXTRACT(SECOND FROM timestamp AT TIME ZONE 'America/New_York') = 0
        )
        """
    ]
    params: list[Any] = []
    if source_start:
        where.append("timestamp >= %s")
        params.append(source_start)
    if source_end:
        where.append("timestamp < %s")
        params.append(source_end)
    where_sql = " WHERE " + " AND ".join(where)
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

    for row in rows:
        if "snapshot_time" not in row:
            raise ValueError("feature rows must include snapshot_time")
        if "input_frame" not in row:
            raise ValueError("feature rows must include input_frame")
        if "prediction_horizon" not in row:
            raise ValueError("feature rows must include prediction_horizon")
        if "market_universe_ref" not in row:
            raise ValueError("feature rows must include market_universe_ref")

    qualified_table = _qualified(target_schema, target_table)
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote_identifier(target_schema)}")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {qualified_table} (
          "snapshot_time" TIMESTAMPTZ NOT NULL,
          "input_frame" TEXT NOT NULL,
          "prediction_horizon" TEXT NOT NULL,
          "market_universe_ref" TEXT NOT NULL,
          "feature_payload_json" JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          PRIMARY KEY ("snapshot_time", "input_frame", "prediction_horizon", "market_universe_ref")
        )
        """
    )
    cursor.execute(f"ALTER TABLE {qualified_table} ADD COLUMN IF NOT EXISTS \"input_frame\" TEXT NOT NULL DEFAULT '1h'")
    cursor.execute(f"ALTER TABLE {qualified_table} ADD COLUMN IF NOT EXISTS \"prediction_horizon\" TEXT NOT NULL DEFAULT '1D'")
    cursor.execute(f"ALTER TABLE {qualified_table} ADD COLUMN IF NOT EXISTS \"market_universe_ref\" TEXT NOT NULL DEFAULT 'layer_01_02_market_context_etf_universe'")
    cursor.execute(f"ALTER TABLE {qualified_table} ADD COLUMN IF NOT EXISTS \"feature_payload_json\" JSONB NOT NULL DEFAULT '{{}}'::jsonb")
    cursor.execute(
        f"""
        DO $$
        DECLARE primary_key_name text;
        BEGIN
          SELECT conname INTO primary_key_name
          FROM pg_constraint
          WHERE conrelid = '{target_schema}.{target_table}'::regclass
            AND contype = 'p';
          IF primary_key_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE {qualified_table} DROP CONSTRAINT %I', primary_key_name);
          END IF;
        END $$;
        """
    )
    cursor.execute(
        f"""
        ALTER TABLE {qualified_table}
        ADD PRIMARY KEY ("snapshot_time", "input_frame", "prediction_horizon", "market_universe_ref")
        """
    )

    insert_sql = f"""
        INSERT INTO {qualified_table} ("snapshot_time", "input_frame", "prediction_horizon", "market_universe_ref", "feature_payload_json")
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT ("snapshot_time", "input_frame", "prediction_horizon", "market_universe_ref") DO UPDATE SET
          "feature_payload_json" = EXCLUDED."feature_payload_json"
    """
    identity_columns = {"snapshot_time", "input_frame", "prediction_horizon", "market_universe_ref"}
    for row in rows:
        payload = {key: value for key, value in row.items() if key not in identity_columns}
        cursor.execute(
            insert_sql,
            [
                row.get("snapshot_time"),
                row.get("input_frame"),
                row.get("prediction_horizon"),
                row.get("market_universe_ref"),
                json.dumps(payload, sort_keys=True, default=str),
            ],
        )


def _parse_time_bound(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET)


def filter_snapshot_times(
    snapshot_times: Sequence[str | datetime],
    *,
    snapshot_start: str | datetime | None = None,
    snapshot_end: str | datetime | None = None,
) -> list[str | datetime]:
    """Return snapshot times inside the requested write window.

    Source reads may include a historical lookback so rolling daily features have
    enough point-in-time context. The feature writer must still emit only the
    requested target window; otherwise a monthly repair run can rewrite historical
    snapshots outside its review boundary.
    """

    start = _parse_time_bound(snapshot_start)
    end = _parse_time_bound(snapshot_end)
    output: list[str | datetime] = []
    for snapshot_time in snapshot_times:
        parsed = _parse_time_bound(snapshot_time)
        if parsed is None:
            continue
        if start is not None and parsed < start:
            continue
        if end is not None and parsed >= end:
            continue
        output.append(snapshot_time)
    return output


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
    snapshot_start: str | None = None,
    snapshot_end: str | None = None,
    input_frames: Sequence[str] = ("1h",),
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
            rows: list[dict[str, Any]] = []
            if snapshot_times is not None:
                rows = generator.generate_rows(inputs, snapshot_times=snapshot_times, input_frames=input_frames)
            else:
                for input_frame in input_frames:
                    bounded_snapshot_times = filter_snapshot_times(
                        generator.infer_snapshot_times(inputs, input_frame=input_frame),
                        snapshot_start=snapshot_start,
                        snapshot_end=snapshot_end,
                    )
                    rows.extend(generator.generate_rows(inputs, snapshot_times=bounded_snapshot_times, input_frames=(input_frame,)))
            write_feature_rows_sql(cursor, rows, target_schema=target_schema, target_table=target_table)
            return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="PostgreSQL URL. Defaults to OPENCLAW_DATABASE_URL or the local OpenClaw DB secret file.")
    parser.add_argument("--source-schema", default="trading_data")
    parser.add_argument("--source-table", default="m01_market_regime_data_acquisition")
    parser.add_argument("--target-schema", default="trading_data")
    parser.add_argument("--target-table", default="m01_market_regime_feature_generation")
    parser.add_argument("--source-start", help="Optional lower timestamp bound for source bars. Include enough lookback for requested features.")
    parser.add_argument("--source-end", help="Optional upper timestamp bound for source bars.")
    parser.add_argument("--universe-csv", type=Path, default=DEFAULT_UNIVERSE_CSV)
    parser.add_argument("--combinations-csv", type=Path, default=DEFAULT_COMBINATIONS_CSV)
    parser.add_argument("--snapshot-time", action="append", help="Optional ISO snapshot time. Repeat for multiple snapshots. Defaults to SPY one-hour source-bar timestamps.")
    parser.add_argument("--snapshot-start", help="Optional lower timestamp bound for inferred snapshot rows. Use with a wider source-start lookback.")
    parser.add_argument("--snapshot-end", help="Optional upper timestamp bound for inferred snapshot rows. The bound is half-open.")
    parser.add_argument("--input-frame", action="append", choices=["1min", "10min", "1h", "1D"], help="Layer 1 input frame to generate. Repeat for multiple frames. Defaults to 1h.")
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
        snapshot_start=args.snapshot_start,
        snapshot_end=args.snapshot_end,
        input_frames=tuple(args.input_frame or ["1h"]),
    )
    print(f"generated {row_count} rows into {args.target_schema}.{args.target_table}")
    return 0
