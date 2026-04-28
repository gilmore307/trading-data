"""SQL table writers for durable trading-data outputs."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from trading_data.source_availability.secrets import load_secret_alias, public_secret_summary

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SqlStorageError(ValueError):
    """Raised when SQL storage configuration or writes are invalid."""


class SqlTableWriter(Protocol):
    """Minimal SQL writer contract used by data bundles."""

    def write_rows(
        self,
        *,
        table: str,
        columns: Sequence[str],
        rows: Sequence[Mapping[str, Any]],
        key_columns: Sequence[str],
    ) -> dict[str, Any]:
        """Write rows to a SQL table and return receipt-safe metadata."""


def _ident(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise SqlStorageError(f"invalid SQL identifier: {name!r}")
    return f'"{name}"'


def _qualified_table(schema: str | None, table: str) -> str:
    if schema:
        return f"{_ident(schema)}.{_ident(table)}"
    return _ident(table)


@dataclass(frozen=True)
class PostgresSqlTableWriter:
    """PostgreSQL writer for accepted durable SQL table contracts.

    The writer intentionally depends on a reviewed storage target instead of a
    local filename. Credentials are resolved from a secret alias at runtime.
    """

    target_id: str
    dsn: str
    schema: str | None = None
    table_owner: str | None = None
    create_table: bool = True
    batch_size: int = 5000
    secret_summary: dict[str, Any] | None = None

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "PostgresSqlTableWriter":
        target = dict(config.get("storage_target") or {})
        if target.get("driver") != "postgresql":
            raise SqlStorageError("storage_target.driver must be 'postgresql' for formal SQL output")
        secret_alias = str(target.get("secret_alias") or "").strip()
        if not secret_alias:
            raise SqlStorageError("storage_target.secret_alias is required")
        secret = load_secret_alias(secret_alias)
        dsn = str(secret.values.get("dsn") or target.get("dsn") or "").strip()
        if not dsn:
            host = secret.values.get("host") or target.get("host")
            database = secret.values.get("database") or target.get("database") or secret.values.get("dbname")
            user = secret.values.get("user") or secret.values.get("username") or target.get("user")
            password = secret.values.get("password") or target.get("password")
            port = secret.values.get("port") or target.get("port") or 5432
            if not (host and database and user and password):
                raise SqlStorageError("PostgreSQL storage secret must provide dsn or host/database/user/password")
            dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        return cls(
            target_id=str(target.get("id") or secret_alias),
            dsn=dsn,
            schema=str(target.get("schema") or "").strip() or None,
            table_owner=str(target.get("table_owner") or "").strip() or None,
            create_table=bool(target.get("create_table", True)),
            batch_size=int(target.get("batch_size", 5000)),
            secret_summary=public_secret_summary(secret),
        )

    def write_rows(
        self,
        *,
        table: str,
        columns: Sequence[str],
        rows: Sequence[Mapping[str, Any]],
        key_columns: Sequence[str],
    ) -> dict[str, Any]:
        if not columns:
            raise SqlStorageError("columns are required")
        if not key_columns:
            raise SqlStorageError("key_columns are required")
        missing_keys = [key for key in key_columns if key not in columns]
        if missing_keys:
            raise SqlStorageError(f"key columns are not output columns: {missing_keys}")
        qualified = _qualified_table(self.schema, table)
        id_columns = [_ident(column) for column in columns]
        id_keys = [_ident(column) for column in key_columns]
        placeholders = ", ".join(["%s"] * len(columns))
        update_columns = [column for column in columns if column not in key_columns]
        if update_columns:
            assignments = ", ".join(f"{_ident(column)} = EXCLUDED.{_ident(column)}" for column in update_columns)
            conflict = f"ON CONFLICT ({', '.join(id_keys)}) DO UPDATE SET {assignments}"
        else:
            conflict = f"ON CONFLICT ({', '.join(id_keys)}) DO NOTHING"
        ddl = _market_regime_table_ddl(qualified) if self.create_table and table == "market_regime_etf_bar" else None
        statement = f"INSERT INTO {qualified} ({', '.join(id_columns)}) VALUES ({placeholders}) {conflict}"
        values = [tuple(row.get(column) for column in columns) for row in rows]
        try:
            import psycopg  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised only in environments without psycopg
            raise SqlStorageError("PostgreSQL SQL output requires psycopg; install psycopg[binary]") from exc
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                if self.schema:
                    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_ident(self.schema)}")
                if ddl:
                    cursor.execute(ddl)
                for start in range(0, len(values), self.batch_size):
                    cursor.executemany(statement, values[start : start + self.batch_size])
            connection.commit()
        return {
            "storage_target_id": self.target_id,
            "driver": "postgresql",
            "schema": self.schema,
            "table": table,
            "qualified_table": f"{self.schema}.{table}" if self.schema else table,
            "rows_written": len(values),
            "secret_alias": self.secret_summary,
        }


def _market_regime_table_ddl(qualified_table: str) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {qualified_table} (
        run_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL,
        open DOUBLE PRECISION,
        high DOUBLE PRECISION,
        low DOUBLE PRECISION,
        close DOUBLE PRECISION,
        volume DOUBLE PRECISION,
        vwap DOUBLE PRECISION,
        trade_count BIGINT,
        created_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (run_id, symbol, timeframe, timestamp)
    )
    """
