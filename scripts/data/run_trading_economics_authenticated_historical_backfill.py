#!/usr/bin/env python3
"""Run authenticated monthly Trading Economics calendar backfill.

This is a bounded historical source-data recovery route. It reuses the
Trading Economics calendar-web feed pipeline, writes only canonical storage
source artifacts, and does not materialize M06 SQL rows or model outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGER_SRC = Path("/root/projects/trading-manager/src")
for path in (REPO_ROOT, MANAGER_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

FEED = "07_feed_trading_economics_calendar_web"
DEFAULT_OUTPUT_ROOT = "/root/projects/trading-storage/storage/01_source_data/monthly_backfill/trading_economics_calendar_web"


@dataclass(frozen=True)
class MonthBackfillResult:
    month: str
    status: str
    run_id: str
    row_count: int
    actual_count: int
    previous_count: int
    consensus_count: int
    forecast_count: int
    saved_paths: tuple[str, ...]
    error: dict[str, str] | None = None


def _next_month(month: str) -> str:
    year, month_num = [int(part) for part in month.split("-", 1)]
    month_num += 1
    if month_num == 13:
        year += 1
        month_num = 1
    return f"{year:04d}-{month_num:02d}"


def _month_start(month: str) -> date:
    year, month_num = [int(part) for part in month.split("-", 1)]
    return date(year, month_num, 1)


def _month_end_exclusive(month: str) -> date:
    return _month_start(_next_month(month))


def _iter_months(start_month: str, end_month: str) -> list[str]:
    months: list[str] = []
    current = start_month
    while current <= end_month:
        months.append(current)
        current = _next_month(current)
    return months


def _default_run_group_id() -> str:
    return "te_authenticated_historical_backfill_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _task_key(*, month: str, output_root: str, write_only_changed: bool) -> dict[str, Any]:
    start = _month_start(month)
    end = _month_end_exclusive(month)
    return {
        "task_id": f"te_authenticated_historical_backfill_{month.replace('-', '_')}",
        "feed": FEED,
        "output_root": output_root,
        "params": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "country": "United States",
            "importance": "3",
            "date_range_mode": "custom",
            "use_authenticated_cookies": True,
            "allow_live_fetch": True,
            "monthly_backfill_bucketed_output": True,
            "write_only_changed_monthly_buckets": bool(write_only_changed),
            "source_materialization_role": "append_to_trading_economics_monthly_backfill",
        },
        "manager_controls": {
            "allow_live_provider_calls": True,
            "autonomous_historical_provider_acquisition": True,
            "allowed_providers": ["trading_economics"],
            "allowed_endpoint_families": ["calendar_web"],
            "max_requests": 1,
            "max_rows": 3000,
            "max_time_window": "P45D",
            "timeout_seconds": 30,
            "retry_policy_ref": "trading-data://provider-policy/trading-economics-authenticated-historical-calendar-monthly",
            "rate_limit_policy_ref": "trading-data://provider-policy/trading-economics-authenticated-historical-calendar-monthly",
            "website_url_persistence": False,
            "database_writes_performed": False,
            "model_activation_performed": False,
            "broker_execution_performed": False,
        },
        "policy_refs": [
            "authenticated_monthly_calendar_page_fetch",
            "append_to_storage_source_only",
            "no_website_url_persistence",
            "no_api_download_or_export_endpoint",
            "no_m06_sql_materialization",
            "no_model_activation",
            "no_broker_execution",
        ],
    }


def _saved_csv_paths(result: Any) -> tuple[str, ...]:
    paths: list[str] = []
    for reference in getattr(result, "references", []) or []:
        path = str(reference)
        if path.endswith("/saved/trading_economics_calendar_event.csv"):
            paths.append(path)
    return tuple(paths)


def _field_counts(paths: tuple[str, ...]) -> tuple[int, int, int, int, int]:
    row_count = 0
    actual_count = 0
    previous_count = 0
    consensus_count = 0
    forecast_count = 0
    for path_text in paths:
        path = Path(path_text)
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                row_count += 1
                actual_count += int(bool(str(row.get("actual") or "").strip()))
                previous_count += int(bool(str(row.get("previous") or "").strip()))
                consensus_count += int(bool(str(row.get("consensus") or "").strip()))
                forecast_count += int(bool(str(row.get("te_forecast") or "").strip()))
    return row_count, actual_count, previous_count, consensus_count, forecast_count


def _run_month(
    *,
    pipeline: Any,
    month: str,
    run_group_id: str,
    output_root: str,
    write_only_changed: bool,
    attempts: int,
    retry_delay_seconds: float,
) -> MonthBackfillResult:
    task_key = _task_key(month=month, output_root=output_root, write_only_changed=write_only_changed)
    last_error: dict[str, str] | None = None
    for attempt in range(1, attempts + 1):
        run_id = f"{run_group_id}_{month.replace('-', '_')}" if attempt == 1 else f"{run_group_id}_{month.replace('-', '_')}_retry{attempt:02d}"
        result = pipeline.run(task_key, run_id=run_id)
        if result.status in {"succeeded", "skipped_no_new_or_changed_rows"}:
            paths = _saved_csv_paths(result)
            row_count, actual_count, previous_count, consensus_count, forecast_count = _field_counts(paths)
            return MonthBackfillResult(
                month=month,
                status=result.status,
                run_id=run_id,
                row_count=row_count,
                actual_count=actual_count,
                previous_count=previous_count,
                consensus_count=consensus_count,
                forecast_count=forecast_count,
                saved_paths=paths,
            )
        error = getattr(result, "details", {}).get("error") if isinstance(getattr(result, "details", None), Mapping) else None
        last_error = {"type": str((error or {}).get("type") or "TradingEconomicsCalendarError"), "message": str((error or {}).get("message") or result.status)}
        if attempt < attempts:
            time.sleep(max(0.0, retry_delay_seconds))
    return MonthBackfillResult(
        month=month,
        status="failed",
        run_id=f"{run_group_id}_{month.replace('-', '_')}",
        row_count=0,
        actual_count=0,
        previous_count=0,
        consensus_count=0,
        forecast_count=0,
        saved_paths=(),
        error=last_error,
    )


def _summary_payload(*, run_group_id: str, months: list[str], results: list[MonthBackfillResult], output_root: str) -> dict[str, Any]:
    failures = [result for result in results if result.status == "failed"]
    return {
        "contract_type": "trading_economics_authenticated_historical_calendar_backfill_status",
        "run_group_id": run_group_id,
        "source_name": "trading_economics_calendar_web",
        "start_month": months[0] if months else None,
        "end_month": months[-1] if months else None,
        "requested_month_count": len(months),
        "completed_month_count": len(results) - len(failures),
        "failed_month_count": len(failures),
        "provider_calls_requested": len(months),
        "storage_mutation_scope": "canonical Trading Economics monthly backfill source artifacts only",
        "field_totals": {
            "rows": sum(result.row_count for result in results),
            "actual": sum(result.actual_count for result in results),
            "previous": sum(result.previous_count for result in results),
            "consensus": sum(result.consensus_count for result in results),
            "forecast": sum(result.forecast_count for result in results),
        },
        "month_results": [asdict(result) for result in results],
        "failed_months": [result.month for result in failures],
        "output_root": output_root,
        "provider_calls_performed": len(results),
        "database_writes_performed": False,
        "codex_review_performed": False,
        "model_training_performed": False,
        "model_activation_performed": False,
        "broker_execution_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-month", required=True)
    parser.add_argument("--end-month", required=True)
    parser.add_argument("--run-group-id", default=None)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--retry-attempts", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=15.0)
    parser.add_argument("--write-only-changed", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--max-months", type=int, default=None)
    args = parser.parse_args(argv)

    months = _iter_months(args.start_month, args.end_month)
    if args.max_months is not None:
        months = months[: max(0, args.max_months)]
    if not months:
        raise SystemExit("no months selected")
    run_group_id = args.run_group_id or _default_run_group_id()
    pipeline = import_module("data_feed.07_feed_trading_economics_calendar_web.pipeline")
    results: list[MonthBackfillResult] = []
    for index, month in enumerate(months, start=1):
        result = _run_month(
            pipeline=pipeline,
            month=month,
            run_group_id=run_group_id,
            output_root=args.output_root,
            write_only_changed=args.write_only_changed,
            attempts=max(1, args.retry_attempts),
            retry_delay_seconds=args.retry_delay_seconds,
        )
        results.append(result)
        print(json.dumps(asdict(result), sort_keys=True), flush=True)
        if index < len(months):
            time.sleep(max(0.0, args.delay_seconds))
    summary = _summary_payload(run_group_id=run_group_id, months=months, results=results, output_root=args.output_root)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["failed_month_count"] and not args.allow_partial:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
