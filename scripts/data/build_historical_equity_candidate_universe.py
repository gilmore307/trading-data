#!/usr/bin/env python3
"""Freeze a static historical replay equity candidate universe from the current pool."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_POOL = Path("/root/projects/trading-storage/main/shared/equity_total_symbol_pool.csv")
DEFAULT_OUTPUT_CSV = Path("/root/projects/trading-storage/main/shared/historical_equity_candidate_universe.csv")
DEFAULT_SYMBOLS_TXT = Path("/root/projects/trading-storage/main/shared/historical_equity_candidate_universe.symbols.txt")
DEFAULT_RECEIPT = Path("/root/projects/trading-storage/storage/02_control_plane/runtime/equity_total_symbol_pool/historical_equity_candidate_universe_build_receipt.json")
DEFAULT_UNIVERSE_POLICY_REF = "fixed_current_realtime_pool_snapshot_for_historical_replay"

OUTPUT_FIELDS = [
    "symbol",
    "name",
    "sector",
    "optionable_underlying_status",
    "replay_candidate_status",
    "replay_candidate_reason",
    "source_pool_as_of_date",
    "in_recent_week_volume_top300",
    "in_market_cap_top300",
    "volume_rank",
    "market_cap_rank",
    "source_refs",
    "freeze_as_of_date",
    "universe_policy_ref",
]


@dataclass(frozen=True)
class HistoricalCandidateRow:
    symbol: str
    name: str
    sector: str
    optionable_underlying_status: str
    replay_candidate_status: str
    replay_candidate_reason: str
    source_pool_as_of_date: str
    in_recent_week_volume_top300: str
    in_market_cap_top300: str
    volume_rank: str
    market_cap_rank: str
    source_refs: str
    freeze_as_of_date: str
    universe_policy_ref: str = DEFAULT_UNIVERSE_POLICY_REF

    def to_csv_row(self) -> dict[str, str]:
        return {field: str(getattr(self, field)) for field in OUTPUT_FIELDS}


def _clean_symbol(value: str) -> str:
    return str(value or "").strip().upper()


def _valid_symbol(symbol: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{str(key): str(value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def build_universe(*, source_pool_csv: Path, freeze_as_of_date: str, universe_policy_ref: str = DEFAULT_UNIVERSE_POLICY_REF) -> tuple[list[HistoricalCandidateRow], dict[str, Any]]:
    rows: list[HistoricalCandidateRow] = []
    seen: set[str] = set()
    source_rows = _read_csv(source_pool_csv)
    for raw in source_rows:
        symbol = _clean_symbol(raw.get("symbol"))
        if not symbol or symbol in seen or not _valid_symbol(symbol):
            continue
        if str(raw.get("pool_membership_status") or "").strip().lower() != "active":
            continue
        rows.append(
            HistoricalCandidateRow(
                symbol=symbol,
                name=str(raw.get("name") or ""),
                sector=str(raw.get("sector") or ""),
                optionable_underlying_status=str(raw.get("optionable_underlying_status") or ""),
                replay_candidate_status="active",
                replay_candidate_reason="active_fixed_current_realtime_pool_snapshot",
                source_pool_as_of_date=str(raw.get("as_of_date") or ""),
                in_recent_week_volume_top300=str(raw.get("in_recent_week_volume_top300") or "false").lower(),
                in_market_cap_top300=str(raw.get("in_market_cap_top300") or "false").lower(),
                volume_rank=str(raw.get("volume_rank") or ""),
                market_cap_rank=str(raw.get("market_cap_rank") or ""),
                source_refs=str(raw.get("source_refs") or ""),
                freeze_as_of_date=freeze_as_of_date,
                universe_policy_ref=universe_policy_ref,
            )
        )
        seen.add(symbol)

    rows.sort(key=lambda row: (int(row.market_cap_rank or "10000"), int(row.volume_rank or "10000"), row.symbol))
    receipt = {
        "contract_type": "historical_equity_candidate_universe_build_receipt",
        "source_pool_csv": str(source_pool_csv),
        "freeze_as_of_date": freeze_as_of_date,
        "universe_policy_ref": universe_policy_ref,
        "source_row_count": len(source_rows),
        "active_candidate_count": len(rows),
        "boundary_note": "This is a fixed historical replay candidate universe seeded from the current realtime total-symbol pool. It is stable replay scope, not point-in-time historical market-wide ranking evidence.",
    }
    return rows, receipt


def write_outputs(rows: list[HistoricalCandidateRow], *, output_csv: Path, symbols_txt: Path, receipt_path: Path, receipt: dict[str, Any]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(row.to_csv_row() for row in rows)
    symbols_txt.parent.mkdir(parents=True, exist_ok=True)
    symbols_txt.write_text("".join(f"{row.symbol}\n" for row in rows), encoding="utf-8")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps({**receipt, "output_csv": str(output_csv), "symbols_txt": str(symbols_txt)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pool-csv", type=Path, default=DEFAULT_SOURCE_POOL)
    parser.add_argument("--freeze-as-of-date", default=date.today().isoformat())
    parser.add_argument("--universe-policy-ref", default=DEFAULT_UNIVERSE_POLICY_REF)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--symbols-txt", type=Path, default=DEFAULT_SYMBOLS_TXT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, receipt = build_universe(
        source_pool_csv=args.source_pool_csv,
        freeze_as_of_date=args.freeze_as_of_date,
        universe_policy_ref=args.universe_policy_ref,
    )
    write_outputs(rows, output_csv=args.output_csv, symbols_txt=args.symbols_txt, receipt_path=args.receipt, receipt=receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
