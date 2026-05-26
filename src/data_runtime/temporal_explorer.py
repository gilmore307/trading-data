"""Temporal Explorer calendar substrate for dashboard and replay alignment."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from data_runtime.config import database_url_file
from data_runtime.exchange_calendar import is_regular_us_equity_session, us_equity_holidays
from feed_availability.secrets import load_secret_alias

ET = ZoneInfo("America/New_York")

CALENDAR_DAY_TABLE = "calendar_day"
CALENDAR_MARKET_SESSION_TABLE = "calendar_market_session"
CALENDAR_SCHEDULED_EVENT_TABLE = "calendar_scheduled_event"
CALENDAR_EVENT_RESULT_TABLE = "calendar_event_result"
CALENDAR_NEWS_EVENT_INDEX_TABLE = "calendar_news_event_index"
CHART_OHLCV_CACHE_TABLE = "chart_ohlcv_cache"

TEMPORAL_TABLES = (
    CALENDAR_DAY_TABLE,
    CALENDAR_MARKET_SESSION_TABLE,
    CALENDAR_SCHEDULED_EVENT_TABLE,
    CALENDAR_EVENT_RESULT_TABLE,
    CALENDAR_NEWS_EVENT_INDEX_TABLE,
    CHART_OHLCV_CACHE_TABLE,
)

SUPPORTED_CHART_TIMEFRAMES = ("10min", "30min", "1h", "1D", "1W")
TIMEFRAME_SECONDS = {
    "10min": 600,
    "30min": 1800,
    "1h": 3600,
    "1D": 86400,
    "1W": 604800,
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class OhlcvInputRow:
    """Minimal bar row accepted by the chart cache aggregator."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    vwap: float | None = None
    source_table: str | None = None


def _ident(name: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"invalid SQL identifier: {name!r}")
    return f'"{name}"'


def _qualified(schema: str, table: str) -> str:
    return f"{_ident(schema)}.{_ident(table)}"


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _coerce_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_calendar_day_rows(start_date: date | str, end_date_exclusive: date | str) -> list[dict[str, Any]]:
    """Build one daily spine row per calendar day."""

    start = _coerce_date(start_date)
    end = _coerce_date(end_date_exclusive)
    rows: list[dict[str, Any]] = []
    day = start
    while day < end:
        next_day = day + timedelta(days=1)
        rows.append(
            {
                "calendar_date": day,
                "timezone": "America/New_York",
                "day_of_week": day.isoweekday(),
                "is_weekend": day.weekday() >= 5,
                "is_month_start": day.day == 1,
                "is_month_end": next_day.month != day.month,
                "is_quarter_start": day.day == 1 and day.month in {1, 4, 7, 10},
                "is_quarter_end": next_day.month != day.month and day.month in {3, 6, 9, 12},
                "is_year_start": day.month == 1 and day.day == 1,
                "is_year_end": day.month == 12 and day.day == 31,
            }
        )
        day = next_day
    return rows


def _holiday_name(day: date) -> str | None:
    holiday_names = {
        observed: name
        for observed, name in (
            (_observed(date(day.year, 1, 1)), "New Year's Day"),
            (_nth_weekday(day.year, 1, 0, 3), "Martin Luther King Jr. Day"),
            (_nth_weekday(day.year, 2, 0, 3), "Washington's Birthday"),
            (_easter_sunday(day.year) - timedelta(days=2), "Good Friday"),
            (_last_weekday(day.year, 5, 0), "Memorial Day"),
            (_observed(date(day.year, 7, 4)), "Independence Day"),
            (_nth_weekday(day.year, 9, 0, 1), "Labor Day"),
            (_nth_weekday(day.year, 11, 3, 4), "Thanksgiving Day"),
            (_observed(date(day.year, 12, 25)), "Christmas Day"),
        )
    }
    if day.year >= 2022:
        holiday_names[_observed(date(day.year, 6, 19))] = "Juneteenth National Independence Day"
    return holiday_names.get(day)


def build_market_session_rows(
    start_date: date | str,
    end_date_exclusive: date | str,
    *,
    venues: Sequence[str] = ("NYSE", "NASDAQ", "CRYPTO_24_7"),
) -> list[dict[str, Any]]:
    """Build reviewed fallback market-session rows.

    NYSE/NASDAQ rows are rule-generated fallback rows. Early closes are not
    inferred here; accepted official rows can later override the same keys.
    """

    start = _coerce_date(start_date)
    end = _coerce_date(end_date_exclusive)
    rows: list[dict[str, Any]] = []
    day = start
    while day < end:
        for venue in venues:
            venue = venue.upper()
            if venue == "CRYPTO_24_7":
                open_at = datetime.combine(day, time(0, 0), tzinfo=UTC)
                close_at = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=UTC)
                rows.append(
                    {
                        "venue": venue,
                        "calendar_date": day,
                        "timezone": "UTC",
                        "is_trading_day": True,
                        "session_type": "crypto_continuous",
                        "open_time": open_at,
                        "close_time": close_at,
                        "holiday_name": None,
                        "source_priority": "deterministic_rule",
                        "source_ref": "trading_data.data_runtime.temporal_explorer",
                    }
                )
                continue
            if venue not in {"NYSE", "NASDAQ"}:
                continue
            holiday = day in us_equity_holidays(day.year)
            weekend = day.weekday() >= 5
            regular = is_regular_us_equity_session(day)
            open_at = datetime.combine(day, time(9, 30), tzinfo=ET).astimezone(UTC) if regular else None
            close_at = datetime.combine(day, time(16, 0), tzinfo=ET).astimezone(UTC) if regular else None
            rows.append(
                {
                    "venue": venue,
                    "calendar_date": day,
                    "timezone": "America/New_York",
                    "is_trading_day": regular,
                    "session_type": "regular" if regular else "weekend" if weekend else "closed",
                    "open_time": open_at,
                    "close_time": close_at,
                    "holiday_name": _holiday_name(day) if holiday else None,
                    "source_priority": "inferred_rule",
                    "source_ref": "trading_data.data_runtime.exchange_calendar",
                }
            )
        day += timedelta(days=1)
    return rows


def aggregate_ohlcv_rows(rows: Iterable[OhlcvInputRow | Mapping[str, Any]], timeframe: str) -> list[dict[str, Any]]:
    """Aggregate minimal OHLCV rows into chart-cache buckets."""

    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"unsupported chart timeframe: {timeframe}")
    buckets: dict[tuple[str, datetime], list[OhlcvInputRow]] = {}
    for row in rows:
        item = _coerce_ohlcv_row(row)
        bucket_start = _bucket_start(item.timestamp, timeframe)
        buckets.setdefault((item.symbol.upper(), bucket_start), []).append(item)
    output: list[dict[str, Any]] = []
    for (symbol, bucket_start), bucket_rows in sorted(buckets.items(), key=lambda item: (item[0][0], item[0][1])):
        ordered = sorted(bucket_rows, key=lambda item: item.timestamp)
        volume = sum(max(item.volume, 0.0) for item in ordered)
        vwap_numerator = sum((item.vwap if item.vwap is not None else item.close) * max(item.volume, 0.0) for item in ordered)
        output.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "bucket_start": bucket_start,
                "bucket_end": _bucket_end(bucket_start, timeframe),
                "open": ordered[0].open,
                "high": max(item.high for item in ordered),
                "low": min(item.low for item in ordered),
                "close": ordered[-1].close,
                "volume": volume,
                "vwap": (vwap_numerator / volume) if volume else None,
                "bar_count": len(ordered),
                "source_table": ordered[0].source_table,
                "quality_flags_json": {},
            }
        )
    return output


def install_temporal_tables(
    *,
    dsn: str | None = None,
    schema: str = "trading_data",
    start_date: date | str = "2016-01-01",
    end_date_exclusive: date | str | None = None,
    include_source10_events: bool = True,
) -> dict[str, Any]:
    """Create temporal tables and upsert the deterministic day/session spine."""

    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - host dependency
        raise RuntimeError("temporal explorer table install requires psycopg") from exc
    if dsn is None:
        dsn = _read_database_url()
    end_date_exclusive = end_date_exclusive or (datetime.now(UTC).date() + timedelta(days=46))
    day_rows = build_calendar_day_rows(start_date, end_date_exclusive)
    session_rows = build_market_session_rows(start_date, end_date_exclusive)
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_ident(schema)}")
            for statement in temporal_table_ddls(schema):
                cursor.execute(statement)
            _upsert_rows(
                cursor,
                schema=schema,
                table=CALENDAR_DAY_TABLE,
                columns=(
                    "calendar_date",
                    "timezone",
                    "day_of_week",
                    "is_weekend",
                    "is_month_start",
                    "is_month_end",
                    "is_quarter_start",
                    "is_quarter_end",
                    "is_year_start",
                    "is_year_end",
                ),
                key_columns=("calendar_date",),
                rows=day_rows,
            )
            _upsert_rows(
                cursor,
                schema=schema,
                table=CALENDAR_MARKET_SESSION_TABLE,
                columns=(
                    "venue",
                    "calendar_date",
                    "timezone",
                    "is_trading_day",
                    "session_type",
                    "open_time",
                    "close_time",
                    "holiday_name",
                    "source_priority",
                    "source_ref",
                ),
                key_columns=("venue", "calendar_date"),
                rows=session_rows,
            )
            scheduled_event_rows = (
                _upsert_scheduled_events_from_source10(cursor, schema=schema)
                if include_source10_events
                else 0
            )
            event_result_rows = (
                _upsert_event_results_from_source10(cursor, schema=schema)
                if include_source10_events
                else 0
            )
            news_event_rows = (
                _upsert_news_events_from_source10(cursor, schema=schema)
                if include_source10_events
                else 0
            )
        connection.commit()
    return {
        "contract_type": "temporal_explorer_table_install_receipt",
        "schema": schema,
        "tables": list(TEMPORAL_TABLES),
        "calendar_day_rows": len(day_rows),
        "market_session_rows": len(session_rows),
        "scheduled_event_rows_from_source10": scheduled_event_rows,
        "event_result_rows_from_source10": event_result_rows,
        "news_event_rows_from_source10": news_event_rows,
        "start_date": str(_coerce_date(start_date)),
        "end_date_exclusive": str(_coerce_date(end_date_exclusive)),
    }


def temporal_table_ddls(schema: str = "trading_data") -> list[str]:
    return [
        _calendar_day_ddl(schema),
        _calendar_market_session_ddl(schema),
        _calendar_scheduled_event_ddl(schema),
        _calendar_event_result_ddl(schema),
        _calendar_news_event_index_ddl(schema),
        _chart_ohlcv_cache_ddl(schema),
    ]


def _calendar_day_ddl(schema: str) -> str:
    table = _qualified(schema, CALENDAR_DAY_TABLE)
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        calendar_date DATE PRIMARY KEY,
        timezone TEXT NOT NULL,
        day_of_week SMALLINT NOT NULL,
        is_weekend BOOLEAN NOT NULL,
        is_month_start BOOLEAN NOT NULL,
        is_month_end BOOLEAN NOT NULL,
        is_quarter_start BOOLEAN NOT NULL,
        is_quarter_end BOOLEAN NOT NULL,
        is_year_start BOOLEAN NOT NULL,
        is_year_end BOOLEAN NOT NULL
    )
    """


def _calendar_market_session_ddl(schema: str) -> str:
    table = _qualified(schema, CALENDAR_MARKET_SESSION_TABLE)
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        venue TEXT NOT NULL,
        calendar_date DATE NOT NULL,
        timezone TEXT NOT NULL,
        is_trading_day BOOLEAN NOT NULL,
        session_type TEXT NOT NULL,
        open_time TIMESTAMPTZ,
        close_time TIMESTAMPTZ,
        holiday_name TEXT,
        source_priority TEXT NOT NULL,
        source_ref TEXT,
        PRIMARY KEY (venue, calendar_date)
    )
    """


def _calendar_scheduled_event_ddl(schema: str) -> str:
    table = _qualified(schema, CALENDAR_SCHEDULED_EVENT_TABLE)
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        event_id TEXT PRIMARY KEY,
        event_date DATE NOT NULL,
        event_time TIMESTAMPTZ,
        event_type TEXT NOT NULL,
        event_scope TEXT NOT NULL,
        symbol TEXT,
        country TEXT,
        source_priority TEXT NOT NULL,
        scheduled_known_at TIMESTAMPTZ NOT NULL,
        source_url TEXT,
        raw_artifact_ref TEXT,
        metadata_json JSONB NOT NULL DEFAULT '{{}}'::jsonb
    )
    """


def _calendar_event_result_ddl(schema: str) -> str:
    table = _qualified(schema, CALENDAR_EVENT_RESULT_TABLE)
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        event_id TEXT NOT NULL,
        released_at TIMESTAMPTZ NOT NULL,
        available_time TIMESTAMPTZ NOT NULL,
        actual_payload JSONB,
        consensus_payload JSONB,
        surprise_payload JSONB,
        source_url TEXT,
        retrieved_at TIMESTAMPTZ NOT NULL,
        raw_artifact_ref TEXT,
        PRIMARY KEY (event_id, released_at, available_time)
    )
    """


def _calendar_news_event_index_ddl(schema: str) -> str:
    table = _qualified(schema, CALENDAR_NEWS_EVENT_INDEX_TABLE)
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        news_event_id TEXT PRIMARY KEY,
        event_date DATE NOT NULL,
        first_seen_at TIMESTAMPTZ NOT NULL,
        source TEXT NOT NULL,
        headline TEXT NOT NULL,
        symbol TEXT,
        event_family_candidate TEXT,
        canonical_event_id TEXT,
        dedup_status TEXT NOT NULL,
        raw_artifact_ref TEXT,
        interpreted_event_ref TEXT
    )
    """


def _chart_ohlcv_cache_ddl(schema: str) -> str:
    table = _qualified(schema, CHART_OHLCV_CACHE_TABLE)
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        bucket_start TIMESTAMPTZ NOT NULL,
        bucket_end TIMESTAMPTZ NOT NULL,
        open DOUBLE PRECISION NOT NULL,
        high DOUBLE PRECISION NOT NULL,
        low DOUBLE PRECISION NOT NULL,
        close DOUBLE PRECISION NOT NULL,
        volume DOUBLE PRECISION,
        vwap DOUBLE PRECISION,
        bar_count INTEGER NOT NULL,
        source_table TEXT,
        quality_flags_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        generated_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (symbol, timeframe, bucket_start)
    )
    """


def _coerce_ohlcv_row(row: OhlcvInputRow | Mapping[str, Any]) -> OhlcvInputRow:
    if isinstance(row, OhlcvInputRow):
        return row
    return OhlcvInputRow(
        symbol=str(row["symbol"]),
        timestamp=_coerce_datetime(row.get("timestamp") or row.get("bucket_start")),
        open=float(row.get("open") if row.get("open") is not None else row.get("bar_open")),
        high=float(row.get("high") if row.get("high") is not None else row.get("bar_high")),
        low=float(row.get("low") if row.get("low") is not None else row.get("bar_low")),
        close=float(row.get("close") if row.get("close") is not None else row.get("bar_close")),
        volume=float(row.get("volume") if row.get("volume") is not None else row.get("bar_volume") or 0.0),
        vwap=float(row["vwap"]) if row.get("vwap") is not None else float(row["bar_vwap"]) if row.get("bar_vwap") is not None else None,
        source_table=str(row.get("source_table") or "") or None,
    )


def _bucket_start(value: datetime, timeframe: str) -> datetime:
    timestamp = value.astimezone(UTC).replace(microsecond=0)
    if timeframe == "1D":
        return datetime(timestamp.year, timestamp.month, timestamp.day, tzinfo=UTC)
    if timeframe == "1W":
        monday = timestamp.date() - timedelta(days=timestamp.weekday())
        return datetime.combine(monday, time(0, 0), tzinfo=UTC)
    seconds = TIMEFRAME_SECONDS[timeframe]
    epoch_seconds = int(timestamp.timestamp())
    return datetime.fromtimestamp(epoch_seconds - (epoch_seconds % seconds), tz=UTC)


def _bucket_end(bucket_start: datetime, timeframe: str) -> datetime:
    return bucket_start + timedelta(seconds=TIMEFRAME_SECONDS[timeframe])


def _read_database_url() -> str:
    path = database_url_file()
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    secret = load_secret_alias("trading_storage_postgres")
    dsn = str(secret.values.get("dsn") or "").strip()
    if dsn:
        return dsn
    host = secret.values.get("host")
    database = secret.values.get("database") or secret.values.get("dbname")
    user = secret.values.get("user") or secret.values.get("username")
    password = secret.values.get("password")
    port = secret.values.get("port") or 5432
    if not (host and database and user and password):
        raise RuntimeError("database secret must provide dsn or host/database/user/password")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _upsert_rows(
    cursor: Any,
    *,
    schema: str,
    table: str,
    columns: Sequence[str],
    key_columns: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    if not rows:
        return
    quoted_columns = [_ident(column) for column in columns]
    placeholders = ", ".join(["%s"] * len(columns))
    assignments = ", ".join(f"{_ident(column)} = EXCLUDED.{_ident(column)}" for column in columns if column not in key_columns)
    conflict = f"ON CONFLICT ({', '.join(_ident(column) for column in key_columns)}) DO UPDATE SET {assignments}"
    statement = f"INSERT INTO {_qualified(schema, table)} ({', '.join(quoted_columns)}) VALUES ({placeholders}) {conflict}"
    values = [tuple(_json_safe(row.get(column)) for column in columns) for row in rows]
    cursor.executemany(statement, values)


def _upsert_scheduled_events_from_source10(cursor: Any, *, schema: str) -> int:
    cursor.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema = %s AND table_name = 'source_10_event_risk_governor'
        ) AS exists
        """,
        (schema,),
    )
    if not bool(cursor.fetchone()[0]):
        return 0
    statement = f"""
    INSERT INTO {_qualified(schema, CALENDAR_SCHEDULED_EVENT_TABLE)} (
        event_id,
        event_date,
        event_time,
        event_type,
        event_scope,
        symbol,
        country,
        source_priority,
        scheduled_known_at,
        source_url,
        raw_artifact_ref,
        metadata_json
    )
    SELECT
        event_id,
        COALESCE(event_time::date, available_time::date) AS event_date,
        event_time,
        COALESCE(NULLIF(event_category_type, ''), 'scheduled_event') AS event_type,
        COALESCE(NULLIF(scope_type, ''), 'market') AS event_scope,
        NULLIF(symbol, '') AS symbol,
        NULL::text AS country,
        COALESCE(NULLIF(source_priority, ''), 'source_10_event_risk_governor') AS source_priority,
        COALESCE(available_time, event_time, now()) AS scheduled_known_at,
        CASE WHEN reference_type IN ('url', 'web_url') THEN reference ELSE NULL END AS source_url,
        NULLIF(source_artifact_path, '') AS raw_artifact_ref,
        jsonb_strip_nulls(jsonb_build_object(
            'title', NULLIF(title, ''),
            'summary', NULLIF(summary, ''),
            'source_name', NULLIF(source_name, ''),
            'coverage_reason', NULLIF(coverage_reason, ''),
            'reference_type', NULLIF(reference_type, ''),
            'reference', NULLIF(reference, '')
        )) AS metadata_json
    FROM {_qualified(schema, "source_10_event_risk_governor")}
    WHERE event_time IS NOT NULL
      AND (
        event_category_type IN ('macro_data', 'earnings_guidance')
        OR source_name = '07_feed_trading_economics_calendar_web'
      )
    ON CONFLICT (event_id) DO UPDATE SET
        event_date = EXCLUDED.event_date,
        event_time = EXCLUDED.event_time,
        event_type = EXCLUDED.event_type,
        event_scope = EXCLUDED.event_scope,
        symbol = EXCLUDED.symbol,
        country = EXCLUDED.country,
        source_priority = EXCLUDED.source_priority,
        scheduled_known_at = EXCLUDED.scheduled_known_at,
        source_url = EXCLUDED.source_url,
        raw_artifact_ref = EXCLUDED.raw_artifact_ref,
        metadata_json = EXCLUDED.metadata_json
    """
    cursor.execute(statement)
    return int(cursor.rowcount or 0)


def _upsert_event_results_from_source10(cursor: Any, *, schema: str) -> int:
    if not _source10_exists(cursor, schema=schema):
        return 0
    statement = f"""
    INSERT INTO {_qualified(schema, CALENDAR_EVENT_RESULT_TABLE)} (
        event_id,
        released_at,
        available_time,
        actual_payload,
        consensus_payload,
        surprise_payload,
        source_url,
        retrieved_at,
        raw_artifact_ref
    )
    SELECT
        event_id,
        COALESCE(available_time, event_time) AS released_at,
        COALESCE(available_time, event_time) AS available_time,
        jsonb_strip_nulls(jsonb_build_object(
            'actual', NULLIF(substring(summary FROM 'actual=([^;]+)'), ''),
            'previous', NULLIF(substring(summary FROM 'previous=([^;]+)'), ''),
            'raw_summary', NULLIF(summary, ''),
            'title', NULLIF(title, '')
        )) AS actual_payload,
        jsonb_strip_nulls(jsonb_build_object(
            'consensus', NULLIF(substring(summary FROM 'consensus=([^;]+)'), ''),
            'te_forecast', NULLIF(substring(summary FROM 'te_forecast=([^;]+)'), '')
        )) AS consensus_payload,
        jsonb_strip_nulls(jsonb_build_object(
            'raw_summary', NULLIF(summary, ''),
            'numeric_surprise_not_computed', true
        )) AS surprise_payload,
        CASE WHEN reference_type IN ('url', 'web_url') THEN reference ELSE NULL END AS source_url,
        COALESCE(available_time, event_time, now()) AS retrieved_at,
        NULLIF(source_artifact_path, '') AS raw_artifact_ref
    FROM {_qualified(schema, "source_10_event_risk_governor")}
    WHERE event_time IS NOT NULL
      AND available_time IS NOT NULL
      AND summary ILIKE '%event_phase=release_result%'
      AND (
        summary ILIKE '%actual=%'
        OR summary ILIKE '%consensus=%'
        OR summary ILIKE '%previous=%'
        OR summary ILIKE '%te_forecast=%'
      )
    ON CONFLICT (event_id, released_at, available_time) DO UPDATE SET
        actual_payload = EXCLUDED.actual_payload,
        consensus_payload = EXCLUDED.consensus_payload,
        surprise_payload = EXCLUDED.surprise_payload,
        source_url = EXCLUDED.source_url,
        retrieved_at = EXCLUDED.retrieved_at,
        raw_artifact_ref = EXCLUDED.raw_artifact_ref
    """
    cursor.execute(statement)
    return int(cursor.rowcount or 0)


def _upsert_news_events_from_source10(cursor: Any, *, schema: str) -> int:
    if not _source10_exists(cursor, schema=schema):
        return 0
    statement = f"""
    INSERT INTO {_qualified(schema, CALENDAR_NEWS_EVENT_INDEX_TABLE)} (
        news_event_id,
        event_date,
        first_seen_at,
        source,
        headline,
        symbol,
        event_family_candidate,
        canonical_event_id,
        dedup_status,
        raw_artifact_ref,
        interpreted_event_ref
    )
    SELECT
        event_id AS news_event_id,
        COALESCE(event_time::date, available_time::date) AS event_date,
        COALESCE(available_time, event_time) AS first_seen_at,
        COALESCE(NULLIF(source_name, ''), 'source_10_event_risk_governor') AS source,
        COALESCE(NULLIF(title, ''), NULLIF(summary, ''), event_id) AS headline,
        NULLIF(symbol, '') AS symbol,
        COALESCE(NULLIF(event_category_type, ''), 'news') AS event_family_candidate,
        NULLIF(canonical_event_id, '') AS canonical_event_id,
        COALESCE(NULLIF(dedup_status, ''), 'indexed') AS dedup_status,
        COALESCE(NULLIF(source_artifact_path, ''), NULLIF(reference, '')) AS raw_artifact_ref,
        NULL::text AS interpreted_event_ref
    FROM {_qualified(schema, "source_10_event_risk_governor")}
    WHERE event_time IS NOT NULL
      AND available_time IS NOT NULL
      AND (
        event_category_type IN ('symbol_news', 'sector_news')
        OR source_name IN ('03_feed_alpaca_news', '05_feed_gdelt_news')
      )
    ON CONFLICT (news_event_id) DO UPDATE SET
        event_date = EXCLUDED.event_date,
        first_seen_at = EXCLUDED.first_seen_at,
        source = EXCLUDED.source,
        headline = EXCLUDED.headline,
        symbol = EXCLUDED.symbol,
        event_family_candidate = EXCLUDED.event_family_candidate,
        canonical_event_id = EXCLUDED.canonical_event_id,
        dedup_status = EXCLUDED.dedup_status,
        raw_artifact_ref = EXCLUDED.raw_artifact_ref,
        interpreted_event_ref = EXCLUDED.interpreted_event_ref
    """
    cursor.execute(statement)
    return int(cursor.rowcount or 0)


def _source10_exists(cursor: Any, *, schema: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema = %s AND table_name = 'source_10_event_risk_governor'
        ) AS exists
        """,
        (schema,),
    )
    return bool(cursor.fetchone()[0])


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return value


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    day = date(year, month, 1)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day + timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    day = date(year + (month // 12), (month % 12) + 1, 1) - timedelta(days=1)
    while day.weekday() != weekday:
        day -= timedelta(days=1)
    return day


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install Temporal Explorer calendar substrate tables.")
    parser.add_argument("--schema", default="trading_data")
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date-exclusive")
    parser.add_argument("--dsn")
    parser.add_argument("--skip-source10-events", action="store_true")
    args = parser.parse_args(argv)
    receipt = install_temporal_tables(
        dsn=args.dsn,
        schema=args.schema,
        start_date=args.start_date,
        end_date_exclusive=args.end_date_exclusive,
        include_source10_events=not args.skip_source10_events,
    )
    json.dump(receipt, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


__all__ = [
    "CALENDAR_DAY_TABLE",
    "CALENDAR_EVENT_RESULT_TABLE",
    "CALENDAR_MARKET_SESSION_TABLE",
    "CALENDAR_NEWS_EVENT_INDEX_TABLE",
    "CALENDAR_SCHEDULED_EVENT_TABLE",
    "CHART_OHLCV_CACHE_TABLE",
    "OhlcvInputRow",
    "SUPPORTED_CHART_TIMEFRAMES",
    "TEMPORAL_TABLES",
    "aggregate_ohlcv_rows",
    "build_calendar_day_rows",
    "build_market_session_rows",
    "install_temporal_tables",
    "main",
    "temporal_table_ddls",
]
