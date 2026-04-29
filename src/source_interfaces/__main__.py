"""CLI for provider/data-kind interface inventory and smoke probes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from source_availability.__main__ import DEFAULT_SEC_USER_AGENT
from source_availability.http import HttpClient
from source_availability.report import report_payload, write_report

from .catalog import INTERFACES
from .probes import interface_payload, probe_many


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m source_interfaces")
    parser.add_argument("--list", action="store_true", help="List provider/data-kind interfaces without network calls.")
    parser.add_argument("--source", help="Filter by source, e.g. alpaca, okx, thetadata, 08_source_sec_company_financials.")
    parser.add_argument("--data-kind", action="append", choices=sorted(INTERFACES), help="Probe one data_kind; repeatable.")
    parser.add_argument("--timeout-seconds", type=int, default=8)
    parser.add_argument("--report-root", type=Path, default=Path("storage/source_interfaces"))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--sec-user-agent", default=os.environ.get("SEC_EDGAR_USER_AGENT", DEFAULT_SEC_USER_AGENT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        payload = {"interfaces": [item for item in interface_payload() if not args.source or item["source"] == args.source]}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    results = probe_many(args.data_kind, args.source, HttpClient(timeout_seconds=args.timeout_seconds), sec_user_agent=args.sec_user_agent)
    if args.no_write:
        print(json.dumps(report_payload(results, mode="live"), indent=2, sort_keys=True))
    else:
        print(write_report(results, mode="live", report_root=args.report_root))
    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
