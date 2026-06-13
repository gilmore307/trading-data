#!/usr/bin/env python3
"""Refresh the shared realtime equity total-symbol pool from TradingView inputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

DEFAULT_OUTPUT_ROOT = Path("/root/projects/trading-storage/storage/01_source_data/realtime/tradingview_equity_screener")
DEFAULT_RECEIPT = Path("/root/projects/trading-storage/storage/02_control_plane/runtime/equity_total_symbol_pool/refresh_receipt.json")
DEFAULT_REVIEWED_ADDITIONS_CSV = Path("/root/projects/trading-storage/main/shared/equity_total_symbol_pool_reviewed_additions.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--per-rank-limit", type=int, default=300)
    parser.add_argument("--optionable-symbols-file", type=Path, default=None)
    parser.add_argument("--reviewed-additions-csv", type=Path, default=DEFAULT_REVIEWED_ADDITIONS_CSV)
    parser.add_argument("--allow-unknown-optionability", action="store_true", default=True)
    parser.add_argument("--strict-optionability", action="store_false", dest="allow_unknown_optionability")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    return parser.parse_args()


def _run(command: list[str]) -> dict:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def main() -> int:
    args = parse_args()
    snapshot_receipt = _run(
        [
            sys.executable,
            "scripts/data/fetch_tradingview_equity_screener.py",
            "--as-of-date",
            args.as_of_date,
            "--per-rank-limit",
            str(args.per_rank_limit),
            "--output-root",
            str(args.output_root),
        ]
    )
    snapshot_csv = Path(snapshot_receipt["output_csv"])
    build_command = [
        sys.executable,
        "scripts/data/build_equity_total_symbol_pool.py",
        "--tradingview-csv",
        str(snapshot_csv),
        "--as-of-date",
        args.as_of_date,
        "--rank-limit",
        str(args.per_rank_limit),
        "--reviewed-additions-csv",
        str(args.reviewed_additions_csv),
    ]
    if args.optionable_symbols_file:
        build_command.extend(["--optionable-symbols-file", str(args.optionable_symbols_file)])
    if args.allow_unknown_optionability:
        build_command.extend(["--allow-unknown-optionability", "--symbols-include-unknown-optionability"])
    build_receipt = _run(build_command)
    receipt = {
        "contract_type": "equity_total_symbol_pool_tradingview_refresh_receipt",
        "as_of_date": args.as_of_date,
        "refresh_interval_minutes": 30,
        "per_rank_limit": args.per_rank_limit,
        "snapshot_receipt": snapshot_receipt,
        "build_receipt": build_receipt,
        "optionability_mode": "allow_unknown" if args.allow_unknown_optionability else "strict_optionable_list",
        "boundary_note": "This refresh performs a bounded TradingView realtime screener snapshot for traded-dollar-value and market-cap ranked equity candidates, then rebuilds the shared calendar symbol pool. It performs no ETF holdings fetches and no broker/account/model activation. Historical replay must use its frozen candidate-universe table instead of reading this mutable realtime pool directly.",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
