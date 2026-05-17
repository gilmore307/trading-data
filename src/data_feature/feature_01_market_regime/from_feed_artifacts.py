"""Materialize Layer 1 feed artifacts and generate market-regime features.

This command is intentionally offline: it reads already-acquired Alpaca bar CSV
artifacts from the local trading-data storage tree, upserts them into
``trading_data.source_01_market_regime``, and then runs the deterministic
``feature_01_market_regime`` SQL generator. It does not call providers.
"""

from __future__ import annotations

import argparse
import csv
import json
from calendar import monthrange
from dataclasses import asdict, dataclass
from pathlib import Path

from data_runtime.config import repo_root, storage_root
from typing import Any, Iterable, Mapping, Sequence

from data_source.source_01_market_regime.pipeline import FIELDS, OUTPUT_TABLE
from storage.sql import PostgresSqlTableWriter, SqlTableWriter

from .sql import DEFAULT_COMBINATIONS_CSV, DEFAULT_UNIVERSE_CSV, _database_url, generate_sql

DEFAULT_STORAGE_ROOT = storage_root()


@dataclass(frozen=True)
class FeedArtifactMaterializationSummary:
    contract_type: str
    month: str
    receipt_count: int
    artifact_count: int
    source_rows_found: int
    source_rows_written: int
    feature_rows_written: int
    provider_calls: int = 0
    model_activation_performed: bool = False
    broker_execution_performed: bool = False

    def summary_row(self) -> dict[str, Any]:
        return asdict(self)


def _month_bounds(month: str) -> tuple[str, str]:
    year_text, month_text = month.split("-", 1)
    year = int(year_text)
    month_number = int(month_text)
    last_day = monthrange(year, month_number)[1]
    return f"{year:04d}-{month_number:02d}-01T00:00:00-05:00", f"{year:04d}-{month_number:02d}-{last_day:02d}T23:59:59-05:00"


def _latest_successful_output(receipt: Mapping[str, Any]) -> str | None:
    runs = [run for run in receipt.get("runs") or [] if isinstance(run, Mapping) and str(run.get("status") or "").lower() == "succeeded"]
    if not runs:
        return None
    latest = runs[-1]
    for output in latest.get("outputs") or []:
        if str(output).endswith("equity_bar.csv"):
            return str(output)
    return None


def discover_feed_artifacts(*, storage_root: Path, month: str, symbols: Sequence[str] = ()) -> list[Path]:
    """Return saved equity_bar.csv artifacts from successful monthly feed receipts."""

    symbol_filter = {symbol.upper() for symbol in symbols}
    receipt_paths = sorted((storage_root / "monthly_backfill" / "alpaca_bars").glob(f"*/{month}/completion_receipt.json"))
    artifacts: list[Path] = []
    for receipt_path in receipt_paths:
        symbol = receipt_path.parent.parent.name.upper()
        if symbol_filter and symbol not in symbol_filter:
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        output = _latest_successful_output(receipt)
        if not output:
            continue
        artifact_path = Path(output)
        if not artifact_path.is_absolute():
            artifact_path = repo_root() / artifact_path
        if artifact_path.exists():
            artifacts.append(artifact_path)
    return artifacts


def _coerce_number(value: str) -> float | int | None:
    if value == "":
        return None
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def read_equity_bar_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = [field for field in FIELDS if field not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"{path} missing required fields: {missing}")
            for raw in reader:
                row = {field: raw.get(field, "") for field in FIELDS}
                for field in ("bar_open", "bar_high", "bar_low", "bar_close", "bar_volume", "bar_vwap", "bar_trade_count"):
                    row[field] = _coerce_number(str(row[field]))
                rows.append(row)
    rows.sort(key=lambda row: (str(row["symbol"]), str(row["timeframe"]), str(row["timestamp"])))
    return rows


def materialize_source_rows(rows: Sequence[Mapping[str, Any]], *, sql_writer: SqlTableWriter | None = None) -> int:
    if not rows:
        return 0
    writer = sql_writer or PostgresSqlTableWriter.from_config({})
    metadata = writer.write_rows(table=OUTPUT_TABLE, columns=FIELDS, rows=rows, key_columns=["symbol", "timeframe", "timestamp"])
    return int(metadata.get("rows_written") or len(rows))


def run_from_feed_artifacts(
    *,
    month: str,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    database_url: str | None = None,
    universe_csv: Path = DEFAULT_UNIVERSE_CSV,
    combinations_csv: Path = DEFAULT_COMBINATIONS_CSV,
    symbols: Sequence[str] = (),
    materialize_only: bool = False,
    dry_run: bool = False,
) -> FeedArtifactMaterializationSummary:
    artifacts = discover_feed_artifacts(storage_root=storage_root, month=month, symbols=symbols)
    rows = read_equity_bar_rows(artifacts)
    source_rows_written = 0 if dry_run else materialize_source_rows(rows)
    feature_rows_written = 0
    if not materialize_only and not dry_run:
        source_start, source_end = _month_bounds(month)
        feature_rows_written = generate_sql(
            database_url=_database_url(database_url),
            universe_csv=universe_csv,
            combinations_csv=combinations_csv,
            source_schema="trading_data",
            source_table="source_01_market_regime",
            target_schema="trading_data",
            target_table="feature_01_market_regime",
            source_start=source_start,
            source_end=source_end,
            snapshot_times=None,
        )
    return FeedArtifactMaterializationSummary(
        contract_type="feature_01_market_regime_from_feed_artifacts",
        month=month,
        receipt_count=len(artifacts),
        artifact_count=len(artifacts),
        source_rows_found=len(rows),
        source_rows_written=source_rows_written,
        feature_rows_written=feature_rows_written,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="YYYY-MM month to materialize/generate.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--database-url")
    parser.add_argument("--universe-csv", type=Path, default=DEFAULT_UNIVERSE_CSV)
    parser.add_argument("--combinations-csv", type=Path, default=DEFAULT_COMBINATIONS_CSV)
    parser.add_argument("--symbol", action="append", default=[], help="Optional symbol filter; repeat for multiple symbols.")
    parser.add_argument("--materialize-only", action="store_true", help="Only upsert source rows; do not generate feature rows.")
    parser.add_argument("--dry-run", action="store_true", help="Read artifacts and count rows without SQL writes.")
    args = parser.parse_args(argv)
    summary = run_from_feed_artifacts(
        month=args.month,
        storage_root=args.storage_root,
        database_url=args.database_url,
        universe_csv=args.universe_csv,
        combinations_csv=args.combinations_csv,
        symbols=args.symbol,
        materialize_only=args.materialize_only,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary.summary_row(), indent=2, sort_keys=True))
    return 0


__all__ = [
    "FeedArtifactMaterializationSummary",
    "discover_feed_artifacts",
    "materialize_source_rows",
    "read_equity_bar_rows",
    "run_from_feed_artifacts",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
