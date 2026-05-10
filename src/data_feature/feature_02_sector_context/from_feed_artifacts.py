"""Materialize Layer 2 feed artifacts and generate sector-context features.

This command is intentionally offline: it reads already-acquired Alpaca bar CSV
artifacts from the local trading-data storage tree, upserts them into the shared
``trading_data.source_01_market_regime`` bar table used by the market/sector
feature stack, and then runs the deterministic ``feature_02_sector_context`` SQL
generator. It does not call providers.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from data_feature.feature_01_market_regime.from_feed_artifacts import (
    DEFAULT_STORAGE_ROOT,
    _month_bounds,
    discover_feed_artifacts,
    materialize_source_rows,
    read_equity_bar_rows,
)

from .sql import DEFAULT_COMBINATIONS_CSV, DEFAULT_UNIVERSE_CSV, _database_url, generate_sql


@dataclass(frozen=True)
class SectorFeedArtifactMaterializationSummary:
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

    def summary_row(self) -> dict[str, object]:
        return asdict(self)


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
) -> SectorFeedArtifactMaterializationSummary:
    """Materialize existing Alpaca artifacts and optionally generate Layer 2 features."""

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
            target_table="feature_02_sector_context",
            source_start=source_start,
            source_end=source_end,
            snapshot_times=None,
        )
    return SectorFeedArtifactMaterializationSummary(
        contract_type="feature_02_sector_context_from_feed_artifacts_v1",
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
    "SectorFeedArtifactMaterializationSummary",
    "run_from_feed_artifacts",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
