#!/usr/bin/env python3
"""Plan or run bounded calendar source maintenance."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.data.run_trading_economics_recent_calendar_refresh import (
    DEFAULT_OUTPUT_ROOT as DEFAULT_TE_OUTPUT_ROOT,
    build_recent_calendar_task_key,
    run_refresh as run_te_refresh,
)
from data_runtime.temporal_explorer import install_temporal_tables

OFFICIAL_FEED = "12_feed_official_calendar_discovery"
DEFAULT_OFFICIAL_OUTPUT_ROOT = "/root/projects/trading-storage/storage/01_source_data/realtime/official_calendar_discovery"
DEFAULT_CALENDAR_SYMBOLS_FILE = Path("/root/projects/trading-storage/main/shared/equity_total_symbol_pool.symbols.txt")
DEFAULT_TE_RELEASE_FETCH_DELAY_MINUTES = 2
DEFAULT_TE_RELEASE_FETCH_MAX_COUNT = 48


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
    if not path.exists():
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
    return Path(raw_path) if raw_path else DEFAULT_CALENDAR_SYMBOLS_FILE


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


def build_official_exchange_calendar_task_key(
    *,
    output_root: str = DEFAULT_OFFICIAL_OUTPUT_ROOT,
    allow_live_fetch: bool = False,
) -> dict[str, Any]:
    return {
        "task_id": "official_calendar_discovery_exchange_calendar",
        "feed": OFFICIAL_FEED,
        "output_root": str(Path(output_root) / "official_exchange_calendar" / "nyse_hours_calendars"),
        "params": {
            "data_kind": "official_exchange_calendar",
            "source_url": "https://www.nyse.com/trade/hours-calendars",
        },
        "manager_controls": {
            "allow_live_provider_calls": bool(allow_live_fetch),
            "realtime_provider_maintenance": bool(allow_live_fetch),
            "allowed_providers": ["official_exchange"],
            "allowed_endpoint_families": ["calendar_discovery"],
            "max_requests": 1,
            "max_rows": 500,
            "max_time_window": "P31D",
            "timeout_seconds": 30,
            "retry_policy_ref": "trading-data://provider-policy/calendar-maintenance-single-request",
            "rate_limit_policy_ref": "trading-data://provider-policy/official-exchange-calendar-maintenance",
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
        "boundary_note": "Official calendar discovery writes source artifacts for calendar_observation only; it does not admit M06 event-pool rows.",
    }


def run_official_exchange_calendar_refresh(
    *,
    run_id: str,
    output_root: str,
    execute_live_fetch: bool,
) -> dict[str, Any]:
    task_key = build_official_exchange_calendar_task_key(
        output_root=output_root,
        allow_live_fetch=execute_live_fetch,
    )
    if not execute_live_fetch:
        return {
            "contract_type": "official_exchange_calendar_refresh_receipt",
            "refresh_status": "planned_requires_execute_live_fetch",
            "run_id": run_id,
            "provider_calls_performed": 0,
            "storage_mutation_performed": False,
            "task_key": task_key,
            "boundary_note": "Plan-only receipt. Add --execute-live-fetch to refresh official exchange calendar artifacts.",
        }
    pipeline = import_module("data_feed.12_feed_official_calendar_discovery.pipeline")
    result = pipeline.run(task_key, run_id=f"{run_id}_official_exchange_calendar")
    return {
        "contract_type": "official_exchange_calendar_refresh_receipt",
        "refresh_status": "succeeded" if result.status == "succeeded" else "failed",
        "run_id": run_id,
        "provider_calls_performed": 1,
        "storage_mutation_performed": True,
        "runs": [{"status": result.status, "row_counts": result.row_counts, "references": result.references, "details": result.details}],
        "task_key": task_key,
        "boundary_note": "Official exchange calendar writes NYSE source-backed holiday and early-close artifacts for calendar_market_session overlays.",
    }


def _te_release_fetch_candidates(te_receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = te_receipt.get("result")
    if not isinstance(result, Mapping):
        return []
    details = result.get("details")
    if not isinstance(details, Mapping):
        return []
    candidates = details.get("release_fetch_candidates")
    if not isinstance(candidates, list):
        return []
    return [dict(candidate) for candidate in candidates if isinstance(candidate, Mapping)]


def _systemd_unit_token(value: str) -> str:
    token = "".join(char.lower() if char.isalnum() else "-" for char in value)
    token = "-".join(part for part in token.split("-") if part)
    return token[:96] or "unknown"


def schedule_te_release_fetches(
    *,
    te_receipt: Mapping[str, Any],
    delay_minutes: int = DEFAULT_TE_RELEASE_FETCH_DELAY_MINUTES,
    max_count: int = DEFAULT_TE_RELEASE_FETCH_MAX_COUNT,
    execute: bool,
) -> dict[str, Any]:
    candidates = _te_release_fetch_candidates(te_receipt)
    now = datetime.now(UTC).replace(microsecond=0)
    task_key = te_receipt.get("task_key")
    output_root = task_key.get("output_root") if isinstance(task_key, Mapping) else None
    scheduled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for candidate in candidates[: max(0, max_count)]:
        raw_fetch_after = str(candidate.get("fetch_after_utc") or "")
        try:
            fetch_after = datetime.fromisoformat(raw_fetch_after.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            skipped.append({"candidate": candidate, "reason": "invalid_fetch_after_utc"})
            continue
        fetch_after = fetch_after + timedelta(minutes=max(0, delay_minutes))
        if fetch_after <= now:
            skipped.append({"candidate": candidate, "reason": "fetch_time_not_future"})
            continue
        seconds = int((fetch_after - now).total_seconds())
        start_date = str(candidate.get("start_date") or "")[:10]
        end_date = str(candidate.get("end_date") or "")[:10]
        if not start_date or not end_date:
            skipped.append({"candidate": candidate, "reason": "missing_fetch_window"})
            continue
        unit_token = _systemd_unit_token(f"{start_date}-{raw_fetch_after}")
        unit_name = f"trading-data-te-release-fetch-{unit_token}"
        run_id = f"te_release_fetch_{unit_token.replace('-', '')}"
        command = [
            "systemd-run",
            "--unit",
            unit_name,
            "--on-active",
            f"{seconds}s",
            "--collect",
            sys.executable,
            str(REPO_ROOT / "scripts" / "data" / "run_trading_economics_recent_calendar_refresh.py"),
            "--run-id",
            run_id,
            "--start-date",
            start_date,
            "--end-date",
            end_date,
            "--output-root",
            str(output_root or DEFAULT_TE_OUTPUT_ROOT),
            "--execute-live-fetch",
        ]
        row = {
            "unit_name": unit_name,
            "run_id": run_id,
            "fetch_after_utc": fetch_after.isoformat().replace("+00:00", "Z"),
            "seconds_until_fetch": seconds,
            "start_date": start_date,
            "end_date": end_date,
            "event_count": int(candidate.get("event_count") or 0),
        }
        if execute:
            completed = subprocess.run(command, capture_output=True, text=True)
            row.update(
                {
                    "return_code": completed.returncode,
                    "stdout": completed.stdout[-1000:],
                    "stderr": completed.stderr[-1000:],
                    "status": "scheduled" if completed.returncode == 0 else "failed",
                }
            )
        else:
            row.update({"command": command, "status": "planned"})
        scheduled.append(row)
    scheduled_count = len([row for row in scheduled if row.get("status") in {"scheduled", "planned"}])
    if not candidates:
        schedule_status = "not_requested"
    elif scheduled_count:
        schedule_status = "scheduled" if execute else "planned"
    else:
        schedule_status = "skipped_no_future_candidates"
    return {
        "contract_type": "trading_economics_release_fetch_schedule",
        "schedule_status": schedule_status,
        "delay_minutes": max(0, delay_minutes),
        "candidate_count": len(candidates),
        "scheduled_count": scheduled_count,
        "scheduled": scheduled,
        "skipped": skipped,
    }


def _official_exchange_calendar_paths(receipt: Mapping[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for run in receipt.get("runs") or []:
        if not isinstance(run, Mapping):
            continue
        for reference in run.get("references") or []:
            path = Path(str(reference))
            if path.name == "official_exchange_calendar.csv":
                paths.append(path)
    return paths


def _temporal_end_date_for(paths: list[Path]) -> str | None:
    latest: date | None = None
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                value = str(row.get("calendar_date") or "")[:10]
                if not value:
                    continue
                day = date.fromisoformat(value)
                latest = day if latest is None or day > latest else latest
    if latest is None:
        return None
    return date(latest.year + 1, 1, 1).isoformat()


def run_calendar_maintenance(
    *,
    run_id: str,
    execute_live_fetch: bool,
    skip_trading_economics: bool,
    te_start_date: str | None,
    te_end_date: str | None,
    te_trailing_days: int,
    te_forward_days: int,
    te_output_root: str,
    nasdaq_earnings_start_date: str | None,
    nasdaq_earnings_forward_days: int,
    official_output_root: str,
    symbols: list[str],
    schedule_te_release_fetches_enabled: bool,
    te_release_fetch_delay_minutes: int,
    te_release_fetch_max_count: int,
) -> dict[str, Any]:
    if skip_trading_economics:
        te = {
            "contract_type": "trading_economics_recent_calendar_refresh_receipt",
            "refresh_status": "skipped",
            "run_id": f"{run_id}_te",
            "provider_calls_performed": 0,
            "storage_mutation_performed": False,
            "boundary_note": "Trading Economics recent/future refresh skipped by calendar maintenance policy.",
        }
    else:
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
    exchange = run_official_exchange_calendar_refresh(
        run_id=run_id,
        output_root=official_output_root,
        execute_live_fetch=execute_live_fetch,
    )
    exchange_paths = _official_exchange_calendar_paths(exchange)
    temporal_install: dict[str, Any] | None = None
    if execute_live_fetch and exchange["refresh_status"] == "succeeded" and exchange_paths:
        temporal_install = install_temporal_tables(
            start_date="2016-01-01",
            end_date_exclusive=_temporal_end_date_for(exchange_paths),
            official_exchange_calendar_paths=exchange_paths,
        )
    te_release_fetch_schedule = None
    if schedule_te_release_fetches_enabled:
        te_release_fetch_schedule = schedule_te_release_fetches(
            te_receipt=te,
            delay_minutes=te_release_fetch_delay_minutes,
            max_count=te_release_fetch_max_count,
            execute=execute_live_fetch and not skip_trading_economics,
        )
    statuses = [status for status in (te["refresh_status"], official["refresh_status"], exchange["refresh_status"]) if status != "skipped"]
    if statuses and all(status == "planned_requires_execute_live_fetch" for status in statuses):
        status = "planned_requires_execute_live_fetch"
    elif statuses and all(status in {"succeeded", "skipped_no_new_or_changed_rows"} for status in statuses):
        status = "succeeded"
    elif not statuses:
        status = "skipped"
    else:
        status = "failed"
    return {
        "contract_type": "calendar_maintenance_refresh_receipt",
        "refresh_status": status,
        "run_id": run_id,
        "components": {
            "trading_economics_recent_calendar": te,
            "official_calendar_discovery": official,
            "official_exchange_calendar": exchange,
            "temporal_explorer_session_overlay": temporal_install,
            "trading_economics_release_fetch_schedule": te_release_fetch_schedule,
        },
        "provider_calls_performed": int(te.get("provider_calls_performed") or 0) + int(official.get("provider_calls_performed") or 0) + int(exchange.get("provider_calls_performed") or 0),
        "storage_mutation_performed": bool(te.get("storage_mutation_performed") or official.get("storage_mutation_performed") or exchange.get("storage_mutation_performed") or temporal_install),
        "boundary_note": "Shared calendar maintenance service; source rows/artifacts only, no M06 event-pool admission.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--execute-live-fetch", action="store_true")
    parser.add_argument("--skip-trading-economics", action="store_true")
    parser.add_argument("--schedule-te-release-fetches", action="store_true")
    parser.add_argument("--te-release-fetch-delay-minutes", type=int, default=DEFAULT_TE_RELEASE_FETCH_DELAY_MINUTES)
    parser.add_argument("--te-release-fetch-max-count", type=int, default=DEFAULT_TE_RELEASE_FETCH_MAX_COUNT)
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
        skip_trading_economics=args.skip_trading_economics,
        te_start_date=args.te_start_date,
        te_end_date=args.te_end_date,
        te_trailing_days=args.te_trailing_days,
        te_forward_days=args.te_forward_days,
        te_output_root=args.te_output_root,
        nasdaq_earnings_start_date=args.nasdaq_earnings_start_date,
        nasdaq_earnings_forward_days=args.nasdaq_earnings_forward_days,
        official_output_root=args.official_output_root,
        symbols=symbols,
        schedule_te_release_fetches_enabled=args.schedule_te_release_fetches,
        te_release_fetch_delay_minutes=args.te_release_fetch_delay_minutes,
        te_release_fetch_max_count=args.te_release_fetch_max_count,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["refresh_status"] in {"succeeded", "planned_requires_execute_live_fetch"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
