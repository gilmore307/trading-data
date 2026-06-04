#!/usr/bin/env python3
"""Refresh the shared equity total symbol pool from screener and ETF holdings inputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

DEFAULT_OUTPUT_ROOT = Path("/root/projects/trading-storage/storage/01_source_data/realtime/tradingview_equity_screener")
DEFAULT_ETF_HOLDINGS_OUTPUT_ROOT = Path("/root/projects/trading-storage/storage/01_source_data/realtime/etf_universe_holdings")
DEFAULT_RECEIPT = Path("/root/projects/trading-storage/storage/02_control_plane/runtime/equity_total_symbol_pool/refresh_receipt.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--per-rank-limit", type=int, default=100)
    parser.add_argument("--optionable-symbols-file", type=Path, default=None)
    parser.add_argument("--allow-unknown-optionability", action="store_true", default=True)
    parser.add_argument("--strict-optionability", action="store_false", dest="allow_unknown_optionability")
    parser.add_argument("--include-etf-holdings", action="store_true", default=True)
    parser.add_argument("--skip-etf-holdings", action="store_false", dest="include_etf_holdings")
    parser.add_argument("--etf-holdings-output-root", type=Path, default=DEFAULT_ETF_HOLDINGS_OUTPUT_ROOT)
    parser.add_argument("--fail-on-partial-etf-holdings", action="store_true")
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
    etf_holdings_receipt = None
    etf_holdings_csv = None
    if args.include_etf_holdings:
        etf_command = [
            sys.executable,
            "scripts/data/fetch_etf_universe_holdings.py",
            "--as-of-date",
            args.as_of_date,
            "--output-root",
            str(args.etf_holdings_output_root),
        ]
        if args.fail_on_partial_etf_holdings:
            etf_command.append("--fail-on-partial")
        etf_holdings_receipt = _run(etf_command)
        etf_holdings_csv = Path(etf_holdings_receipt["output_csv"])
    build_command = [
        sys.executable,
        "scripts/data/build_equity_total_symbol_pool.py",
        "--tradingview-csv",
        str(snapshot_csv),
        "--as-of-date",
        args.as_of_date,
    ]
    if etf_holdings_csv is not None:
        build_command.extend(["--layer2-holdings-csv", str(etf_holdings_csv)])
    if args.optionable_symbols_file:
        build_command.extend(["--optionable-symbols-file", str(args.optionable_symbols_file)])
    if args.allow_unknown_optionability:
        build_command.extend(["--allow-unknown-optionability", "--symbols-include-unknown-optionability"])
    build_receipt = _run(build_command)
    receipt = {
        "contract_type": "equity_total_symbol_pool_tradingview_refresh_receipt",
        "as_of_date": args.as_of_date,
        "snapshot_receipt": snapshot_receipt,
        "etf_holdings_receipt": etf_holdings_receipt,
        "build_receipt": build_receipt,
        "optionability_mode": "allow_unknown" if args.allow_unknown_optionability else "strict_optionable_list",
        "boundary_note": "This refresh performs bounded TradingView and official ETF issuer holdings source fetches, then builds the shared calendar symbol pool; it performs no broker/account/model activation.",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
