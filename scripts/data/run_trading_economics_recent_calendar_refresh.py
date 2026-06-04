#!/usr/bin/env python3
"""Plan or run the bounded Trading Economics recent-calendar refresh."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import Any

FEED = "07_feed_trading_economics_calendar_web"
DEFAULT_OUTPUT_ROOT = "/root/projects/trading-storage/storage/01_source_data/monthly_backfill/trading_economics_calendar_web"


def _today_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _default_run_id() -> str:
    return "te_recent_calendar_refresh_" + _today_utc().strftime("%Y%m%dT%H%M%SZ")


def build_recent_calendar_task_key(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    trailing_days: int = 7,
    forward_days: int = 35,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    allow_live_fetch: bool = False,
    persist_failure_diagnostics: bool = True,
) -> dict[str, Any]:
    """Build a bounded recent/future-calendar task key with provider controls."""

    if trailing_days < 0:
        raise ValueError("trailing_days must be >= 0")
    if forward_days < 1:
        raise ValueError("forward_days must be >= 1")
    today = _today_utc().date()
    start = start_date or (today - timedelta(days=trailing_days)).isoformat()
    end = end_date or (today + timedelta(days=forward_days)).isoformat()
    return {
        "task_id": "trading_economics_recent_calendar_refresh",
        "feed": FEED,
        "output_root": output_root,
        "params": {
            "start_date": start,
            "end_date": end,
            "country": "United States",
            "importance": "3",
            "date_range_mode": "recent",
            "use_authenticated_cookies": False,
            "allow_live_fetch": bool(allow_live_fetch),
            "persist_failure_diagnostics": bool(persist_failure_diagnostics),
            "monthly_backfill_bucketed_output": True,
            "source_materialization_role": "append_to_trading_economics_monthly_backfill",
        },
        "manager_controls": {
            "allow_live_provider_calls": bool(allow_live_fetch),
            "realtime_provider_maintenance": bool(allow_live_fetch),
            "allowed_providers": ["trading_economics"],
            "allowed_endpoint_families": ["calendar_web"],
            "max_requests": 1,
            "max_rows": 2000,
            "max_time_window": "P45D",
            "timeout_seconds": 30,
            "retry_policy_ref": "trading-data://provider-policy/recent-calendar-single-request",
            "rate_limit_policy_ref": "trading-data://provider-policy/trading-economics-recent-calendar",
        },
    }


def build_plan_receipt(*, task_key: dict[str, Any], run_id: str) -> dict[str, Any]:
    return {
        "contract_type": "trading_economics_recent_calendar_refresh_receipt",
        "refresh_status": "planned_requires_execute_live_fetch",
        "run_id": run_id,
        "task_key": task_key,
        "provider_calls_performed": 0,
        "storage_mutation_performed": False,
        "boundary_note": "Plan-only receipt. Add --execute-live-fetch to perform the bounded calendar-page fetch; source URLs are not persisted.",
    }


def run_refresh(*, task_key: dict[str, Any], run_id: str, execute_live_fetch: bool) -> dict[str, Any]:
    if not execute_live_fetch:
        return build_plan_receipt(task_key=task_key, run_id=run_id)
    pipeline = import_module("data_feed.07_feed_trading_economics_calendar_web.pipeline")
    result = pipeline.run(task_key, run_id=run_id)
    return {
        "contract_type": "trading_economics_recent_calendar_refresh_receipt",
        "refresh_status": result.status,
        "run_id": run_id,
        "task_key": task_key,
        "result": result.__dict__,
        "provider_calls_performed": 1 if result.status == "succeeded" else 0,
        "storage_mutation_performed": True,
        "boundary_note": "Recent/future TE calendar acquisition writes canonical storage source rows only; it does not persist source URLs or populate Layer 10 SQL rows.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--trailing-days", type=int, default=7)
    parser.add_argument("--forward-days", type=int, default=35)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--execute-live-fetch", action="store_true")
    parser.add_argument("--no-failure-diagnostics", action="store_true")
    parser.add_argument("--write-task-key", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = args.run_id or _default_run_id()
    task_key = build_recent_calendar_task_key(
        start_date=args.start_date,
        end_date=args.end_date,
        trailing_days=args.trailing_days,
        forward_days=args.forward_days,
        output_root=args.output_root,
        allow_live_fetch=args.execute_live_fetch,
        persist_failure_diagnostics=not args.no_failure_diagnostics,
    )
    if args.write_task_key is not None:
        args.write_task_key.parent.mkdir(parents=True, exist_ok=True)
        args.write_task_key.write_text(json.dumps(task_key, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = run_refresh(task_key=task_key, run_id=run_id, execute_live_fetch=args.execute_live_fetch)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["refresh_status"] in {"succeeded", "planned_requires_execute_live_fetch"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
