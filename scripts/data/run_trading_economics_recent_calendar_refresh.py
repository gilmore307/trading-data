#!/usr/bin/env python3
"""Plan or run the bounded Trading Economics recent-calendar refresh."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGER_SRC = Path("/root/projects/trading-manager/src")
for path in (REPO_ROOT, MANAGER_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

FEED = "07_feed_trading_economics_calendar_web"
DEFAULT_OUTPUT_ROOT = "/root/projects/trading-storage/storage/01_source_data/monthly_backfill/trading_economics_calendar_web"
DEFAULT_RELEASE_POLL_INTERVAL_SECONDS = 5
DEFAULT_RELEASE_POLL_TIMEOUT_SECONDS = 60


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
    use_authenticated_cookies: bool = False,
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
            "use_authenticated_cookies": bool(use_authenticated_cookies),
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


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")
    tmp.replace(path)


def _rows_from_reference(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    if path.suffix == ".jsonl":
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if isinstance(payload, Mapping):
                    rows.append({str(key): str(value or "") for key, value in payload.items()})
        return rows
    if path.suffix == ".csv":
        import csv

        with path.open(newline="", encoding="utf-8") as handle:
            return [{str(key): str(value or "") for key, value in row.items()} for row in csv.DictReader(handle)]
    return []


def _receipt_has_released_value(receipt: Mapping[str, Any]) -> bool:
    result = receipt.get("result")
    if not isinstance(result, Mapping):
        return False
    for reference in result.get("references") or []:
        path = Path(str(reference))
        if path.name != "trading_economics_calendar_event.csv" and path.name != "trading_economics_calendar_event.jsonl":
            continue
        for row in _rows_from_reference(path):
            if str(row.get("actual") or "").strip():
                return True
    return False


def _web_search_fallback_queries(task_key: Mapping[str, Any], fallback_queries: list[str]) -> list[str]:
    queries = [query.strip() for query in fallback_queries if query.strip()]
    if queries:
        return queries
    params = task_key.get("params") if isinstance(task_key.get("params"), Mapping) else {}
    start_date = str(params.get("start_date") or "").strip()
    country = str(params.get("country") or "United States").strip()
    return [f"{country} economic data release actual {start_date}"]


def run_web_search_fallback(
    *,
    task_key: Mapping[str, Any],
    run_id: str,
    fallback_queries: list[str],
    search_fn: Callable[..., list[Any]] | None = None,
) -> dict[str, Any]:
    queries = _web_search_fallback_queries(task_key, fallback_queries)
    output_root = Path(str(task_key.get("output_root") or DEFAULT_OUTPUT_ROOT))
    output_path = output_root / "_manifests" / "release_fetch_fallbacks" / run_id / "provisional_macro_release_web_search.json"
    retrieval_time_utc = _today_utc().isoformat().replace("+00:00", "Z")
    search_status = "succeeded"
    query_results: list[dict[str, Any]] = []
    error: dict[str, str] | None = None
    try:
        if search_fn is None:
            from trading_web_search import brave_search

            search_fn = brave_search
        for query in queries:
            results = search_fn(query, count=5, country="US", freshness="pd")
            query_results.append(
                {
                    "query": query,
                    "results": [asdict(result) if is_dataclass(result) else dict(result) for result in results],
                }
            )
    except Exception as exc:
        search_status = "failed"
        error = {"type": type(exc).__name__, "message": str(exc)}
    payload = {
        "contract_type": "provisional_macro_release_web_search",
        "run_id": run_id,
        "retrieval_time_utc": retrieval_time_utc,
        "search_status": search_status,
        "queries": queries,
        "query_results": query_results,
        "source_role": "provisional_realtime_decision_fallback",
        "replacement_policy": "Use only until formal Trading Economics release rows are captured; do not merge into TE-origin source rows.",
        "task_key": task_key,
        "error": error,
    }
    _atomic_write_json(output_path, payload)
    return {
        "contract_type": "provisional_macro_release_web_search_receipt",
        "fallback_status": search_status,
        "reference": str(output_path),
        "query_count": len(queries),
        "result_count": sum(len(row.get("results") or []) for row in query_results),
        "error": error,
    }


def run_refresh(*, task_key: dict[str, Any], run_id: str, execute_live_fetch: bool) -> dict[str, Any]:
    if not execute_live_fetch:
        return build_plan_receipt(task_key=task_key, run_id=run_id)
    pipeline = import_module("data_feed.07_feed_trading_economics_calendar_web.pipeline")
    result = pipeline.run(task_key, run_id=run_id)
    storage_mutation = result.status == "succeeded" and bool(result.details.get("storage_mutation_performed", True))
    return {
        "contract_type": "trading_economics_recent_calendar_refresh_receipt",
        "refresh_status": result.status,
        "run_id": run_id,
        "task_key": task_key,
        "result": result.__dict__,
        "provider_calls_performed": 1 if result.status in {"succeeded", "skipped_no_new_or_changed_rows"} else 0,
        "storage_mutation_performed": storage_mutation,
        "boundary_note": "Recent/future TE calendar acquisition writes canonical storage source rows only when new or changed release-preview facts are observed; it does not persist source URLs or populate M06 event-governance SQL rows.",
    }


def run_release_poll(
    *,
    task_key: dict[str, Any],
    run_id: str,
    execute_live_fetch: bool,
    poll_interval_seconds: int,
    poll_timeout_seconds: int,
    fallback_web_search_after_timeout: bool,
    fallback_queries: list[str],
) -> dict[str, Any]:
    if not execute_live_fetch:
        receipt = build_plan_receipt(task_key=task_key, run_id=run_id)
        receipt["release_poll"] = {
            "poll_status": "planned_requires_execute_live_fetch",
            "poll_interval_seconds": max(1, poll_interval_seconds),
            "poll_timeout_seconds": max(0, poll_timeout_seconds),
            "fallback_web_search_after_timeout": bool(fallback_web_search_after_timeout),
            "fallback_queries": _web_search_fallback_queries(task_key, fallback_queries),
        }
        return receipt
    deadline = time.monotonic() + max(0, poll_timeout_seconds)
    interval = max(1, poll_interval_seconds)
    attempts: list[dict[str, Any]] = []
    latest: dict[str, Any] | None = None
    attempt_index = 0
    while True:
        attempt_index += 1
        attempt_run_id = run_id if attempt_index == 1 else f"{run_id}_retry{attempt_index:02d}"
        latest = run_refresh(task_key=task_key, run_id=attempt_run_id, execute_live_fetch=True)
        has_released_value = _receipt_has_released_value(latest)
        attempts.append(
            {
                "attempt": attempt_index,
                "run_id": attempt_run_id,
                "refresh_status": latest["refresh_status"],
                "storage_mutation_performed": latest["storage_mutation_performed"],
                "released_value_available": has_released_value,
            }
        )
        if has_released_value:
            latest["provider_calls_performed"] = len(attempts)
            latest["release_poll"] = {
                "poll_status": "te_released_value_available",
                "attempts": attempts,
                "poll_interval_seconds": interval,
                "poll_timeout_seconds": max(0, poll_timeout_seconds),
            }
            return latest
        if time.monotonic() >= deadline:
            break
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
    fallback = None
    if fallback_web_search_after_timeout:
        fallback = run_web_search_fallback(task_key=task_key, run_id=run_id, fallback_queries=fallback_queries)
    assert latest is not None
    latest["release_poll"] = {
        "poll_status": "fallback_requested" if fallback else "timed_out_without_released_value",
        "attempts": attempts,
        "poll_interval_seconds": interval,
        "poll_timeout_seconds": max(0, poll_timeout_seconds),
        "fallback_web_search": fallback,
    }
    if fallback:
        latest["provider_calls_performed"] = len(attempts) + int(fallback["query_count"])
        latest["storage_mutation_performed"] = True
    else:
        latest["provider_calls_performed"] = len(attempts)
    return latest


def receipt_exit_success(receipt: Mapping[str, Any]) -> bool:
    release_poll = receipt.get("release_poll")
    if isinstance(release_poll, Mapping):
        poll_status = release_poll.get("poll_status")
        if poll_status in {"te_released_value_available", "planned_requires_execute_live_fetch"}:
            return True
        fallback = release_poll.get("fallback_web_search")
        return isinstance(fallback, Mapping) and fallback.get("fallback_status") == "succeeded"
    return receipt.get("refresh_status") in {"succeeded", "skipped_no_new_or_changed_rows", "planned_requires_execute_live_fetch"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--trailing-days", type=int, default=7)
    parser.add_argument("--forward-days", type=int, default=35)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--execute-live-fetch", action="store_true")
    parser.add_argument("--release-poll-until-value", action="store_true")
    parser.add_argument("--release-poll-interval-seconds", type=int, default=DEFAULT_RELEASE_POLL_INTERVAL_SECONDS)
    parser.add_argument("--release-poll-timeout-seconds", type=int, default=DEFAULT_RELEASE_POLL_TIMEOUT_SECONDS)
    parser.add_argument("--fallback-web-search-after-timeout", action="store_true")
    parser.add_argument("--fallback-query", action="append", default=[])
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
    if args.release_poll_until_value:
        receipt = run_release_poll(
            task_key=task_key,
            run_id=run_id,
            execute_live_fetch=args.execute_live_fetch,
            poll_interval_seconds=args.release_poll_interval_seconds,
            poll_timeout_seconds=args.release_poll_timeout_seconds,
            fallback_web_search_after_timeout=args.fallback_web_search_after_timeout,
            fallback_queries=args.fallback_query,
        )
    else:
        receipt = run_refresh(task_key=task_key, run_id=run_id, execute_live_fetch=args.execute_live_fetch)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt_exit_success(receipt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
