#!/usr/bin/env python3
"""Run due Trading Economics release fetch jobs from the shared queue."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.data.run_calendar_maintenance_refresh import (
    _load_release_fetch_queue,
    _write_release_fetch_queue,
    release_fetch_queue_path,
)
from scripts.data.run_trading_economics_recent_calendar_refresh import (
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_RELEASE_POLL_INTERVAL_SECONDS,
    DEFAULT_RELEASE_POLL_TIMEOUT_SECONDS,
    build_recent_calendar_task_key,
    receipt_exit_success,
    run_release_poll,
)

DEFAULT_MAX_DUE_JOBS = 8


def _now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _parse_utc(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _receipt_summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    release_poll = receipt.get("release_poll")
    return {
        "refresh_status": receipt.get("refresh_status"),
        "provider_calls_performed": receipt.get("provider_calls_performed"),
        "storage_mutation_performed": receipt.get("storage_mutation_performed"),
        "release_poll": release_poll if isinstance(release_poll, Mapping) else None,
    }


def run_release_fetch_queue(
    *,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    execute_live_fetch: bool,
    max_due_jobs: int = DEFAULT_MAX_DUE_JOBS,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or _now_utc()
    queue_path = release_fetch_queue_path(output_root)
    payload = _load_release_fetch_queue(queue_path)
    items = [dict(item) for item in payload.get("items", []) if isinstance(item, Mapping)]
    due_limit = max(0, max_due_jobs)
    processed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    due_seen = 0

    for item in items:
        status = str(item.get("status") or "pending")
        if status != "pending":
            continue
        fetch_after = _parse_utc(str(item.get("fetch_after_utc") or ""))
        if fetch_after is None:
            item["status"] = "failed"
            item["completed_at_utc"] = now.isoformat().replace("+00:00", "Z")
            item["last_error"] = "invalid_fetch_after_utc"
            skipped.append({"job_id": item.get("job_id"), "reason": "invalid_fetch_after_utc"})
            continue
        if fetch_after > now:
            continue
        if due_seen >= due_limit:
            continue
        due_seen += 1
        run_id = str(item.get("run_id") or item.get("job_id") or "te_release_fetch")
        start_date = str(item.get("start_date") or "")[:10]
        end_date = str(item.get("end_date") or "")[:10]
        if not start_date or not end_date:
            item["status"] = "failed"
            item["completed_at_utc"] = now.isoformat().replace("+00:00", "Z")
            item["last_error"] = "missing_fetch_window"
            skipped.append({"job_id": item.get("job_id"), "reason": "missing_fetch_window"})
            continue
        task_key = build_recent_calendar_task_key(
            start_date=start_date,
            end_date=end_date,
            output_root=output_root,
            allow_live_fetch=execute_live_fetch,
            persist_failure_diagnostics=True,
        )
        if execute_live_fetch:
            receipt = run_release_poll(
                task_key=task_key,
                run_id=run_id,
                execute_live_fetch=True,
                poll_interval_seconds=int(item.get("poll_interval_seconds") or DEFAULT_RELEASE_POLL_INTERVAL_SECONDS),
                poll_timeout_seconds=int(item.get("poll_timeout_seconds") or DEFAULT_RELEASE_POLL_TIMEOUT_SECONDS),
                fallback_web_search_after_timeout=True,
                fallback_queries=[str(query) for query in item.get("fallback_queries") or []],
            )
            item["status"] = "completed" if receipt_exit_success(receipt) else "failed"
            item["completed_at_utc"] = now.isoformat().replace("+00:00", "Z")
            item["attempt_count"] = int(item.get("attempt_count") or 0) + 1
            item["last_result"] = _receipt_summary(receipt)
            processed.append({"job_id": item.get("job_id"), "status": item["status"], "run_id": run_id})
        else:
            processed.append({"job_id": item.get("job_id"), "status": "planned", "run_id": run_id})

    if execute_live_fetch:
        payload.update(
            {
                "contract_type": "trading_economics_release_fetch_queue",
                "schema_version": 1,
                "updated_at_utc": now.isoformat().replace("+00:00", "Z"),
                "output_root": output_root,
                "items": items,
            }
        )
        _write_release_fetch_queue(queue_path, payload)

    if processed:
        run_status = "processed_due_jobs" if execute_live_fetch else "planned_due_jobs"
    elif skipped:
        run_status = "updated_invalid_jobs" if execute_live_fetch else "planned_invalid_jobs"
    else:
        run_status = "idle_no_due_jobs"
    return {
        "contract_type": "trading_economics_release_fetcher_receipt",
        "run_status": run_status,
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "queue_path": str(queue_path),
        "execute_live_fetch": execute_live_fetch,
        "max_due_jobs": due_limit,
        "processed_count": len(processed),
        "skipped_count": len(skipped),
        "pending_count": len([item for item in items if item.get("status") == "pending"]),
        "processed": processed,
        "skipped": skipped,
        "side_effects": {
            "provider_calls": bool(execute_live_fetch and processed),
            "storage_source_write": bool(execute_live_fetch and processed),
            "broker_execution": False,
            "account_mutation": False,
            "model_activation": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--execute-live-fetch", action="store_true")
    parser.add_argument("--max-due-jobs", type=int, default=DEFAULT_MAX_DUE_JOBS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_release_fetch_queue(
        output_root=args.output_root,
        execute_live_fetch=args.execute_live_fetch,
        max_due_jobs=args.max_due_jobs,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["run_status"] in {"processed_due_jobs", "planned_due_jobs", "idle_no_due_jobs", "updated_invalid_jobs"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
