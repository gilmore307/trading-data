#!/usr/bin/env python3
"""Plan or run bounded calendar source maintenance."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable

from scripts.data.run_trading_economics_recent_calendar_refresh import (
    DEFAULT_OUTPUT_ROOT as DEFAULT_TE_OUTPUT_ROOT,
    build_recent_calendar_task_key,
    run_refresh as run_te_refresh,
)

OFFICIAL_FEED = "12_feed_official_calendar_discovery"
DEFAULT_OFFICIAL_OUTPUT_ROOT = "/root/projects/trading-storage/storage/01_source_data/realtime/official_calendar_discovery"


def _now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _default_run_id() -> str:
    return "calendar_maintenance_" + _now_utc().strftime("%Y%m%dT%H%M%SZ")


def _dates(start: date, forward_days: int) -> Iterable[date]:
    for offset in range(forward_days + 1):
        yield start + timedelta(days=offset)


def _symbols_from_file(path: Path | None) -> list[str]:
    if path is None:
        return []
    text = path.read_text(encoding="utf-8")
    symbols: list[str] = []
    for raw in text.replace("\r", "\n").replace(",", "\n").replace(";", "\n").splitlines():
        symbol = raw.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _default_symbols_file() -> Path | None:
    raw_path = os.environ.get("TRADING_DATA_CALENDAR_SYMBOLS_FILE")
    return Path(raw_path) if raw_path else None


def build_nasdaq_earnings_task_key(
    *,
    calendar_date: str,
    output_root: str = DEFAULT_OFFICIAL_OUTPUT_ROOT,
    symbols: list[str] | None = None,
    allow_live_fetch: bool = False,
) -> dict[str, Any]:
    return {
        "task_id": f"official_calendar_discovery_nasdaq_earnings_{calendar_date}",
        "feed": OFFICIAL_FEED,
        "output_root": str(Path(output_root) / "nasdaq_earnings_calendar" / calendar_date),
        "params": {
            "data_kind": "nasdaq_earnings_calendar",
            "date": calendar_date,
            "symbols": symbols or [],
        },
        "manager_controls": {
            "allow_live_provider_calls": bool(allow_live_fetch),
            "realtime_provider_maintenance": bool(allow_live_fetch),
            "allowed_providers": ["nasdaq"],
            "allowed_endpoint_families": ["calendar_discovery"],
            "max_requests": 1,
            "max_rows": 5000,
            "max_time_window": "P2D",
            "timeout_seconds": 30,
            "retry_policy_ref": "trading-data://provider-policy/calendar-maintenance-single-request",
            "rate_limit_policy_ref": "trading-data://provider-policy/nasdaq-calendar-maintenance",
        },
    }


def run_nasdaq_earnings_refresh(
    *,
    run_id: str,
    start_date: str | None,
    forward_days: int,
    output_root: str,
    symbols: list[str],
    execute_live_fetch: bool,
) -> dict[str, Any]:
    if forward_days < 0:
        raise ValueError("nasdaq_earnings_forward_days must be >= 0")
    start = date.fromisoformat(start_date) if start_date else _now_utc().date()
    task_keys = [
        build_nasdaq_earnings_task_key(
            calendar_date=day.isoformat(),
            output_root=output_root,
            symbols=symbols,
            allow_live_fetch=execute_live_fetch,
        )
        for day in _dates(start, forward_days)
    ]
    if not execute_live_fetch:
        return {
            "contract_type": "official_calendar_discovery_refresh_receipt",
            "refresh_status": "planned_requires_execute_live_fetch",
            "run_id": run_id,
            "provider_calls_performed": 0,
            "storage_mutation_performed": False,
            "task_keys": task_keys,
            "boundary_note": "Plan-only receipt. Add --execute-live-fetch to refresh official calendar discovery artifacts.",
        }
    pipeline = import_module("data_feed.12_feed_official_calendar_discovery.pipeline")
    runs: list[dict[str, Any]] = []
    for task_key in task_keys:
        calendar_date = str(task_key["params"]["date"])
        result = pipeline.run(task_key, run_id=f"{run_id}_nasdaq_earnings_{calendar_date.replace('-', '')}")
        runs.append({"calendar_date": calendar_date, "status": result.status, "row_counts": result.row_counts, "references": result.references, "details": result.details})
    failed = [run for run in runs if run["status"] != "succeeded"]
    return {
        "contract_type": "official_calendar_discovery_refresh_receipt",
        "refresh_status": "failed" if failed else "succeeded",
        "run_id": run_id,
        "provider_calls_performed": len(runs),
        "storage_mutation_performed": True,
        "runs": runs,
        "boundary_note": "Official calendar discovery writes source artifacts for calendar_observation only; it does not admit Layer 10 event-pool rows.",
    }


def run_calendar_maintenance(
    *,
    run_id: str,
    execute_live_fetch: bool,
    te_start_date: str | None,
    te_end_date: str | None,
    te_trailing_days: int,
    te_forward_days: int,
    te_output_root: str,
    nasdaq_earnings_start_date: str | None,
    nasdaq_earnings_forward_days: int,
    official_output_root: str,
    symbols: list[str],
) -> dict[str, Any]:
    te_task_key = build_recent_calendar_task_key(
        start_date=te_start_date,
        end_date=te_end_date,
        trailing_days=te_trailing_days,
        forward_days=te_forward_days,
        output_root=te_output_root,
        allow_live_fetch=execute_live_fetch,
        persist_failure_diagnostics=True,
    )
    te = run_te_refresh(task_key=te_task_key, run_id=f"{run_id}_te", execute_live_fetch=execute_live_fetch)
    official = run_nasdaq_earnings_refresh(
        run_id=run_id,
        start_date=nasdaq_earnings_start_date,
        forward_days=nasdaq_earnings_forward_days,
        output_root=official_output_root,
        symbols=symbols,
        execute_live_fetch=execute_live_fetch,
    )
    statuses = [te["refresh_status"], official["refresh_status"]]
    if all(status == "planned_requires_execute_live_fetch" for status in statuses):
        status = "planned_requires_execute_live_fetch"
    elif all(status == "succeeded" for status in statuses):
        status = "succeeded"
    else:
        status = "failed"
    return {
        "contract_type": "calendar_maintenance_refresh_receipt",
        "refresh_status": status,
        "run_id": run_id,
        "components": {
            "trading_economics_recent_calendar": te,
            "official_calendar_discovery": official,
        },
        "provider_calls_performed": int(te.get("provider_calls_performed") or 0) + int(official.get("provider_calls_performed") or 0),
        "storage_mutation_performed": bool(te.get("storage_mutation_performed") or official.get("storage_mutation_performed")),
        "boundary_note": "Shared calendar maintenance service; source rows/artifacts only, no Layer 10 event-pool admission.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--execute-live-fetch", action="store_true")
    parser.add_argument("--te-start-date", default=None)
    parser.add_argument("--te-end-date", default=None)
    parser.add_argument("--te-trailing-days", type=int, default=7)
    parser.add_argument("--te-forward-days", type=int, default=35)
    parser.add_argument("--te-output-root", default=DEFAULT_TE_OUTPUT_ROOT)
    parser.add_argument("--nasdaq-earnings-start-date", default=None)
    parser.add_argument("--nasdaq-earnings-forward-days", type=int, default=1)
    parser.add_argument("--official-output-root", default=DEFAULT_OFFICIAL_OUTPUT_ROOT)
    parser.add_argument("--symbols-file", type=Path, default=_default_symbols_file())
    parser.add_argument("--symbol", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = args.run_id or _default_run_id()
    symbols = _symbols_from_file(args.symbols_file)
    for symbol in args.symbol:
        cleaned = str(symbol).strip().upper()
        if cleaned and cleaned not in symbols:
            symbols.append(cleaned)
    receipt = run_calendar_maintenance(
        run_id=run_id,
        execute_live_fetch=args.execute_live_fetch,
        te_start_date=args.te_start_date,
        te_end_date=args.te_end_date,
        te_trailing_days=args.te_trailing_days,
        te_forward_days=args.te_forward_days,
        te_output_root=args.te_output_root,
        nasdaq_earnings_start_date=args.nasdaq_earnings_start_date,
        nasdaq_earnings_forward_days=args.nasdaq_earnings_forward_days,
        official_output_root=args.official_output_root,
        symbols=symbols,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["refresh_status"] in {"succeeded", "planned_requires_execute_live_fetch"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
