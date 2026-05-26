#!/usr/bin/env python3
"""Return the retired Trading Economics recent-refresh plan receipt.

The active macro source is the canonical storage snapshot under
trading-storage. The website subscription is expired, so this wrapper no
longer performs live Trading Economics fetches.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

FEED = "07_feed_trading_economics_calendar_web"
DEFAULT_OUTPUT_ROOT = "storage/monthly_backfill/trading_economics_calendar_web"


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
    persist_failure_diagnostics: bool = True,
) -> dict[str, Any]:
    """Build the retired recent-calendar inventory task key."""

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
            "persist_failure_diagnostics": bool(persist_failure_diagnostics),
            "monthly_backfill_bucketed_output": True,
            "source_materialization_role": "append_to_trading_economics_monthly_backfill",
        },
        "manager_controls": {
            "allow_live_provider_calls": False,
            "realtime_provider_maintenance": False,
            "allowed_providers": [],
            "allowed_endpoint_families": [],
            "max_requests": 0,
            "max_rows": 2000,
            "max_time_window": "P45D",
            "timeout_seconds": 30,
            "retry_policy_ref": "retired",
            "rate_limit_policy_ref": "retired",
        },
    }


def build_plan_receipt(*, task_key: dict[str, Any], run_id: str) -> dict[str, Any]:
    return {
        "contract_type": "trading_economics_recent_calendar_refresh_receipt",
        "refresh_status": "retired_storage_source_only",
        "run_id": run_id,
        "task_key": task_key,
        "provider_calls_performed": 0,
        "storage_mutation_performed": False,
        "boundary_note": (
            "Trading Economics website refresh is retired because the subscription is expired. "
            "Use trading-storage/storage/01_source_data/monthly_backfill/"
            "trading_economics_calendar_web as the only macro source."
        ),
    }


def run_refresh(*, task_key: dict[str, Any], run_id: str, execute_live_fetch: bool) -> dict[str, Any]:
    if not execute_live_fetch:
        return build_plan_receipt(task_key=task_key, run_id=run_id)
    return {
        "contract_type": "trading_economics_recent_calendar_refresh_receipt",
        "refresh_status": "rejected_retired_storage_source_only",
        "run_id": run_id,
        "task_key": task_key,
        "provider_calls_performed": 0,
        "storage_mutation_performed": False,
        "boundary_note": (
            "--execute-live-fetch is disabled. The TE website subscription is expired; "
            "use the canonical storage TE snapshot instead."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--trailing-days", type=int, default=7)
    parser.add_argument("--forward-days", type=int, default=35)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--execute-live-fetch", action="store_true", help="Rejected; TE website refresh is retired.")
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
        persist_failure_diagnostics=not args.no_failure_diagnostics,
    )
    if args.write_task_key is not None:
        args.write_task_key.parent.mkdir(parents=True, exist_ok=True)
        args.write_task_key.write_text(json.dumps(task_key, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = run_refresh(task_key=task_key, run_id=run_id, execute_live_fetch=args.execute_live_fetch)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["refresh_status"] == "retired_storage_source_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
