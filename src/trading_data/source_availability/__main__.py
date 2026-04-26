"""CLI for bounded source availability probes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .http import HttpClient
from .probes import PROBES
from .registry import SOURCES, STATUS_FIELDS
from .report import ProbeResult, report_payload, write_report


DEFAULT_SEC_USER_AGENT = (
    "trading-data-source-availability/0.1 "
    "contact=local-research@example.invalid"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m trading_data.source_availability",
        description="Run bounded smoke probes for registered trading-data sources.",
    )
    parser.add_argument("--list", action="store_true", help="List registered source probes.")
    parser.add_argument("--dry-run", action="store_true", help="Emit planned probes without network calls.")
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(SOURCES),
        help="Source to probe. Can be passed more than once. Defaults to all sources.",
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path("data/storage/source_availability"),
        help="Directory for JSON reports.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=8,
        help="Per-request timeout for live probes.",
    )
    parser.add_argument(
        "--sec-user-agent",
        default=os.environ.get("SEC_EDGAR_USER_AGENT", DEFAULT_SEC_USER_AGENT),
        help="Identifying SEC EDGAR User-Agent. May also be set with SEC_EDGAR_USER_AGENT.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print JSON to stdout instead of writing data/storage/source_availability.",
    )
    return parser


def selected_sources(source_args: list[str] | None) -> list[str]:
    return source_args or list(SOURCES.keys())


def list_sources(source_args: list[str] | None) -> list[dict[str, object]]:
    return [
        {
            "source": candidate.source,
            "display_name": candidate.display_name,
            "data_kind_candidates": list(candidate.data_kind_candidates),
            "access": candidate.access,
            "secret_alias": candidate.secret_alias,
            "docs_url": candidate.docs_url,
        }
        for key, candidate in SOURCES.items()
        if key in selected_sources(source_args)
    ]


def dry_run_results(source_args: list[str] | None) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    for source in selected_sources(source_args):
        candidate = SOURCES[source]
        results.append(
            ProbeResult.skipped(
                candidate,
                "dry-run; no network call made",
            )
        )
    return results


def run_probes(args: argparse.Namespace) -> list[ProbeResult]:
    client = HttpClient(timeout_seconds=args.timeout_seconds)
    results: list[ProbeResult] = []
    for source in selected_sources(args.source):
        results.append(PROBES[source](client, args.sec_user_agent))
    return results


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        print(json.dumps({"sources": list_sources(args.source), "status_fields": STATUS_FIELDS}, indent=2))
        return 0

    mode = "dry-run" if args.dry_run else "live"
    results = dry_run_results(args.source) if args.dry_run else run_probes(args)
    if args.no_write:
        print(json.dumps(report_payload(results, mode=mode), indent=2, sort_keys=True))
    else:
        path = write_report(results, mode=mode, report_root=args.report_root)
        print(str(path))
    failed = [result for result in results if result.status == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
