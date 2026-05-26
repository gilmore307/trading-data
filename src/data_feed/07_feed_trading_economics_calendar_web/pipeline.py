"""Trading Economics visible calendar-page interface feed.

This feed intentionally handles only normal website-visible calendar rows. It
must not call Trading Economics API or download/export endpoints. Historical
custom-window fetches use visible-page date/filter cookies and do not require
authenticated website cookies by default; realtime/recent fetches use the
logged-out recent page without authentication cookies.
"""

from __future__ import annotations

import csv
import html
import json
import re
import urllib.parse
from io import StringIO
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Mapping

from feed_availability.http import HttpClient
from feed_availability.sanitize import sanitize_url, sanitize_value
from data_runtime.provider_policy import require_provider_execution_allowed
from data_runtime.config import resolve_output_root, trading_economics_cookie_jar
from data_runtime.io import atomic_write_json, atomic_write_text, write_receipt_bundle

FEED = "07_feed_trading_economics_calendar_web"
SOURCE_URL = "https://tradingeconomics.com/united-states/calendar"
ET = ZoneInfo("America/New_York")
FIELDS = [
    "event_time",
    "country",
    "event",
    "source_event_type",
    "reference",
    "actual",
    "previous",
    "consensus",
    "te_forecast",
    "revised",
    "importance",
    "symbol",
    "source_url",
]


@dataclass(frozen=True)
class FeedContext:
    task_key: dict[str, Any]
    run_dir: Path
    cleaned_dir: Path
    saved_dir: Path
    receipt_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepResult:
    status: str
    references: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FetchedPage:
    html_text: str
    source_url: str
    fetched_at_utc: str


class TradingEconomicsCalendarError(ValueError):
    """Raised for invalid Trading Economics calendar tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> FeedContext:
    if task_key.get("feed") != FEED:
        raise TradingEconomicsCalendarError(f"task_key.feed must be {FEED}")
    output_root = resolve_output_root(task_key, default_task_id=f"{FEED}_task")
    params = dict(task_key.get("params") or {})
    if params.get("monthly_backfill_bucketed_output"):
        run_dir = output_root / "_manifests" / "recent_refresh_runs" / run_id
        receipt_path = output_root / "_manifests" / "recent_refresh_completion_receipt.json"
    else:
        run_dir = output_root / "runs" / run_id
        receipt_path = output_root / "completion_receipt.json"
    return FeedContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", receipt_path, {"run_id": run_id, "started_at": _now_utc(), "output_root": str(output_root)})


def _date_param(params: Mapping[str, Any], key: str, default: date) -> date:
    value = params.get(key)
    if value in (None, ""):
        return default
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise TradingEconomicsCalendarError(f"params.{key} must be YYYY-MM-DD") from exc


def _window(params: Mapping[str, Any]) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    start = _date_param(params, "start_date", today.replace(day=1))
    end = _date_param(params, "end_date", today)
    if end < start:
        raise TradingEconomicsCalendarError("params.end_date must be >= start_date")
    if (end - start).days > int(params.get("max_window_days", 45)):
        raise TradingEconomicsCalendarError("Trading Economics web interface window is capped; use one month or smaller")
    return start, end


def _range_mode(params: Mapping[str, Any]) -> str:
    mode = str(params.get("date_range_mode") or params.get("range_mode") or "custom").strip().lower()
    if mode not in {"custom", "recent"}:
        raise TradingEconomicsCalendarError("params.date_range_mode must be 'custom' or 'recent'")
    return mode


def _use_authenticated_cookies(params: Mapping[str, Any]) -> bool:
    value = params.get("use_authenticated_cookies")
    if value is None:
        value = params.get("authenticated_cookies")
    if value is None:
        return False
    return bool(value)


def _cookie_header(params: Mapping[str, Any], cookie_jar: Path | None = None) -> str:
    cookie_by_name: dict[str, str] = {}
    use_authenticated = _use_authenticated_cookies(params)
    cookie_jar = Path(cookie_jar) if cookie_jar is not None else trading_economics_cookie_jar()
    if use_authenticated and cookie_jar.exists():
        for line in cookie_jar.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookie_by_name[parts[5]] = parts[6]
    if _range_mode(params) == "custom":
        start, end = _window(params)
        cookie_by_name["cal-custom-range"] = f"{start.isoformat()} 00:00|{end.isoformat()} 00:00"
        cookie_by_name["calendar-range"] = "0"
        cookie_by_name["calendar-importance"] = str(params.get("importance") or "3")
        offset_minutes = int(datetime.combine(start, datetime.min.time(), ET).utcoffset().total_seconds() // 60)
        cookie_by_name["cal-timezone-offset"] = str(offset_minutes)
    return "; ".join(f"{name}={value}" for name, value in cookie_by_name.items())


def _build_url(params: Mapping[str, Any]) -> str:
    if _range_mode(params) == "recent":
        return SOURCE_URL
    start, end = _window(params)
    query = urllib.parse.urlencode({"importance": str(params.get("importance") or "3"), "start": start.isoformat(), "end": end.isoformat()})
    return SOURCE_URL + "?" + query


def fetch(context: FeedContext) -> tuple[StepResult, FetchedPage]:
    params = dict(context.task_key.get("params") or {})
    source_url = str(params.get("source_url") or _build_url(params))
    html_path = params.get("html_path")
    if html_path:
        page = Path(str(html_path)).read_text(encoding="utf-8")
        fetched = FetchedPage(page, source_url, _now_utc())
    elif params.get("html"):
        fetched = FetchedPage(str(params["html"]), source_url, _now_utc())
    elif params.get("allow_live_fetch"):
        start, end = _window(params)
        require_provider_execution_allowed(
            context.task_key,
            provider="trading_economics",
            endpoint_family="calendar_web",
            requested_requests=1,
            requested_start=start.isoformat(),
            requested_end=end.isoformat(),
        )
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml",
        }
        cookie_header = _cookie_header(params)
        if cookie_header:
            headers["Cookie"] = cookie_header
        result = HttpClient(timeout_seconds=int(params.get("timeout_seconds", 30))).get(source_url, headers=headers)
        if result.status is None:
            raise TradingEconomicsCalendarError(f"visible page fetch failed before HTTP response: {result.error_type}: {result.error_message}")
        if result.status < 200 or result.status >= 300:
            raise TradingEconomicsCalendarError(f"visible page fetch returned HTTP {result.status}: {result.error_message or result.text()[:240]}")
        fetched = FetchedPage(result.text(), result.url, _now_utc())
    else:
        raise TradingEconomicsCalendarError("provide params.html_path/html, or set allow_live_fetch=true for a bounded visible-page fetch")
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "feed": "07_feed_trading_economics_calendar_web",
        "source_url": sanitize_url(fetched.source_url),
        "country": str(params.get("country") or "United States"),
        "importance": str(params.get("importance") or "3"),
        "fetched_at_utc": fetched.fetched_at_utc,
        "persistence": "final CSV only; raw page not persisted by default",
        "boundary": "visible web page only; no API or download/export endpoint",
        "date_range_mode": _range_mode(params),
        "use_authenticated_cookies": _use_authenticated_cookies(params),
    }
    path = context.run_dir / "request_manifest.json"
    atomic_write_json(path, sanitize_value(manifest))
    return StepResult("succeeded", [str(path)], {"html_pages": 1}, details={"source_url": source_url}), fetched


def _clean_cell(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _table_rows(html_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html_text, flags=re.I | re.S):
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html, flags=re.I | re.S)
        cleaned = [_clean_cell(cell) for cell in cells]
        if cleaned:
            rows.append(cleaned)
    return rows


def _header_index(header: list[str]) -> dict[str, int]:
    aliases = {
        "date": "event_time",
        "time": "event_time",
        "country": "country",
        "event": "event",
        "calendar": "event",
        "category": "source_event_type",
        "source_event_type": "source_event_type",
        "reference": "reference",
        "actual": "actual",
        "previous": "previous",
        "consensus": "consensus",
        "forecast": "te_forecast",
        "te forecast": "te_forecast",
        "revised": "revised",
        "importance": "importance",
        "symbol": "symbol",
    }
    result: dict[str, int] = {}
    for idx, cell in enumerate(header):
        key = aliases.get(cell.lower().strip())
        if key:
            result[key] = idx
    return result


def _attr(tag: str, name: str) -> str:
    match = re.search(rf"\b{name}=(['\"])(.*?)\1", tag, flags=re.I | re.S)
    return html.unescape(match.group(2)).strip() if match else ""


def _first_text(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.I | re.S)
    return _clean_cell(match.group(match.lastindex or 1)) if match else ""


def _event_time_from_row(row_html: str, fallback_date: str) -> str:
    date_match = re.search(r"<td\b[^>]*class=(['\"])[^'\"]*(\d{4}-\d{2}-\d{2})[^'\"]*\1", row_html, flags=re.I | re.S)
    date_text = date_match.group(2) if date_match else ""
    time_text = _first_text(r"<span\b[^>]*class=(['\"])[^'\"]*calendar-date[^'\"]*\1[^>]*>(.*?)</span>", row_html)
    if date_text and time_text:
        try:
            return datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %I:%M %p").replace(tzinfo=ET).isoformat()
        except ValueError:
            pass
    return fallback_date


def _parse_calendar_data_rows(html_text: str, *, source_url: str, default_country: str, default_importance: str) -> list[dict[str, str]]:
    date_markers = [(match.start(), _clean_cell(match.group(1))) for match in re.finditer(r"<th\b[^>]*colspan=['\"]3['\"][^>]*>(.*?)</th>", html_text, flags=re.I | re.S)]
    row_matches = list(re.finditer(r"<tr\b[^>]*\bdata-url=(['\"]).*?\1[^>]*>", html_text, flags=re.I | re.S))
    if not row_matches:
        return []
    parsed: list[dict[str, str]] = []
    date_i = 0
    for idx, row_match in enumerate(row_matches):
        while date_i + 1 < len(date_markers) and date_markers[date_i + 1][0] < row_match.start():
            date_i += 1
        fallback_date = date_markers[date_i][1] if date_markers else ""
        end = row_matches[idx + 1].start() if idx + 1 < len(row_matches) else len(html_text)
        row_html = html_text[row_match.start():end]
        tag = row_match.group(0)
        event = _first_text(r"<a\b[^>]*class=(['\"])[^'\"]*calendar-event[^'\"]*\1[^>]*>(.*?)</a>", row_html) or _clean_cell(_attr(tag, "data-event")).title()
        if not event:
            continue
        parsed.append({
            "event_time": _event_time_from_row(row_html, fallback_date),
            "country": (_clean_cell(_attr(tag, "data-country")).title() or default_country),
            "event": event,
            "source_event_type": _clean_cell(_attr(tag, "data-category")),
            "reference": _first_text(r"<span\b[^>]*class=(['\"])[^'\"]*calendar-reference[^'\"]*\1[^>]*>(.*?)</span>", row_html),
            "actual": _first_text(r"<span\b[^>]*id=['\"]actual['\"][^>]*>(.*?)</span>", row_html),
            "previous": _first_text(r"<span\b[^>]*id=['\"]previous['\"][^>]*>(.*?)</span>", row_html),
            "consensus": _first_text(r"<span\b[^>]*id=['\"]consensus['\"][^>]*>(.*?)</span>", row_html),
            "te_forecast": _first_text(r"<span\b[^>]*id=['\"]forecast['\"][^>]*>(.*?)</span>", row_html),
            "revised": _first_text(r"<span\b[^>]*id=['\"]revised['\"][^>]*>(.*?)</span>", row_html),
            "importance": default_importance,
            "symbol": "",
            "source_url": sanitize_url(source_url),
        })
    return parsed


def parse_calendar_rows(html_text: str, *, source_url: str, default_country: str, default_importance: str) -> list[dict[str, str]]:
    parsed = _parse_calendar_data_rows(html_text, source_url=source_url, default_country=default_country, default_importance=default_importance)
    if parsed:
        return parsed
    rows = _table_rows(html_text)
    if not rows:
        return []
    header_i = next((i for i, row in enumerate(rows) if {"actual", "previous"}.intersection({cell.lower() for cell in row})), -1)
    if header_i < 0:
        return []
    index = _header_index(rows[header_i])
    parsed = []
    for row in rows[header_i + 1 :]:
        if len(row) < 4:
            continue
        def at(name: str) -> str:
            idx = index.get(name)
            return row[idx] if idx is not None and idx < len(row) else ""
        event = at("event") or (row[2] if len(row) > 2 else "")
        if not event or event.lower() in {"event", "calendar", "previous"}:
            continue
        parsed.append({
            "event_time": at("event_time") or row[0],
            "country": at("country") or default_country,
            "event": event,
            "source_event_type": at("source_event_type"),
            "reference": at("reference"),
            "actual": at("actual"),
            "previous": at("previous"),
            "consensus": at("consensus"),
            "te_forecast": at("te_forecast"),
            "revised": at("revised"),
            "importance": at("importance") or default_importance,
            "symbol": at("symbol"),
            "source_url": sanitize_url(source_url),
        })
    return parsed


def _event_date(row: Mapping[str, str]) -> date | None:
    value = str(row.get("event_time") or "").strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(value, "%A %B %d %Y").date()
        except ValueError:
            return None


def _row_in_window(row: Mapping[str, str], *, start: date, end: date) -> bool:
    parsed = _event_date(row)
    if parsed is None:
        return False
    return start <= parsed < end


def _event_month(row: Mapping[str, str]) -> str:
    parsed = _event_date(row)
    if parsed is None:
        raise TradingEconomicsCalendarError("cannot bucket Trading Economics row without parseable event_time")
    return parsed.strftime("%Y-%m")


def _diagnostic_excerpt(html_text: str, *, max_chars: int = 4000) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = _clean_cell(text)
    text = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[redacted-email]", text, flags=re.I)
    text = re.sub(r"(?i)(token|secret|password|authorization|cookie)=([^\s&;]+)", r"\1=[redacted]", text)
    return text[:max_chars] + ("...[truncated]" if len(text) > max_chars else "")


def _write_failure_diagnostics(
    context: FeedContext,
    fetched: FetchedPage,
    *,
    parsed_rows: list[dict[str, str]],
    start: date,
    end: date,
    out_of_window_count: int,
) -> None:
    params = dict(context.task_key.get("params") or {})
    if not params.get("persist_failure_diagnostics"):
        return
    html_text = fetched.html_text
    diagnostics_dir = context.run_dir / "diagnostics"
    date_markers = [_clean_cell(match.group(1)) for match in re.finditer(r"<th\b[^>]*colspan=['\"]3['\"][^>]*>(.*?)</th>", html_text, flags=re.I | re.S)]
    payload = {
        "contract_type": "trading_economics_calendar_web_failure_diagnostic",
        "feed": FEED,
        "reason": "zero_parseable_in_window_calendar_rows",
        "source_url": sanitize_url(fetched.source_url),
        "window": {"start_date": start.isoformat(), "end_date_exclusive": end.isoformat()},
        "html_length": len(html_text),
        "parsed_rows_count": len(parsed_rows),
        "in_window_rows_count": 0,
        "out_of_window_rows_skipped": out_of_window_count,
        "structural_counts": {
            "table_tags": len(re.findall(r"<table\b", html_text, flags=re.I)),
            "tr_tags": len(re.findall(r"<tr\b", html_text, flags=re.I)),
            "data_url_rows": len(re.findall(r"<tr\b[^>]*\bdata-url=", html_text, flags=re.I | re.S)),
            "calendar_event_class": len(re.findall(r"calendar-event", html_text, flags=re.I)),
            "actual_cells": len(re.findall(r"id=['\"]actual['\"]", html_text, flags=re.I)),
            "previous_cells": len(re.findall(r"id=['\"]previous['\"]", html_text, flags=re.I)),
            "consensus_cells": len(re.findall(r"id=['\"]consensus['\"]", html_text, flags=re.I)),
            "forecast_cells": len(re.findall(r"id=['\"]forecast['\"]", html_text, flags=re.I)),
            "date_markers": len(date_markers),
            "requested_start_year_mentions": html_text.count(start.strftime("%Y")),
        },
        "page_markers": {
            "mentions_login": bool(re.search(r"login|sign in", html_text, flags=re.I)),
            "mentions_captcha": bool(re.search(r"captcha|cloudflare|verify you are human", html_text, flags=re.I)),
            "mentions_calendar": bool(re.search(r"calendar", html_text, flags=re.I)),
            "mentions_united_states": bool(re.search(r"united states", html_text, flags=re.I)),
        },
        "date_marker_samples": sanitize_value(date_markers[:8]),
        "parsed_row_samples": sanitize_value(parsed_rows[:5]),
        "html_text_excerpt": _diagnostic_excerpt(html_text),
        "persistence": "sanitized diagnostic excerpt and structural counters only; cookies/request headers/raw page are not persisted",
    }
    atomic_write_json(diagnostics_dir / "te_calendar_failure_diagnostic.json", payload)


def clean(context: FeedContext, fetched: FetchedPage) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    start, end = _window(params)
    parsed_rows = parse_calendar_rows(fetched.html_text, source_url=fetched.source_url, default_country=str(params.get("country") or "United States"), default_importance=str(params.get("importance") or "3"))
    rows = [row for row in parsed_rows if _row_in_window(row, start=start, end=end)]
    out_of_window_count = len(parsed_rows) - len(rows)
    if not rows:
        _write_failure_diagnostics(context, fetched, parsed_rows=parsed_rows, start=start, end=end, out_of_window_count=out_of_window_count)
        raise TradingEconomicsCalendarError("Trading Economics page produced zero parseable in-window calendar rows")
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    path = context.cleaned_dir / "trading_economics_calendar_event.jsonl"
    atomic_write_text(path, "".join(json.dumps(sanitize_value(row), sort_keys=True) + "\n" for row in rows))
    schema = context.cleaned_dir / "schema.json"
    atomic_write_json(schema, {"trading_economics_calendar_event": FIELDS, "row_count": len(rows)})
    warnings = [f"out_of_window_calendar_rows_skipped={out_of_window_count}"] if out_of_window_count else []
    return StepResult("succeeded", [str(path), str(schema)], {"trading_economics_calendar_event": len(rows)}, warnings=warnings, details={"columns": FIELDS, "out_of_window_calendar_rows_skipped": out_of_window_count})


def save(context: FeedContext, clean_result: StepResult) -> StepResult:
    rows = [json.loads(line) for line in (context.cleaned_dir / "trading_economics_calendar_event.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    params = dict(context.task_key.get("params") or {})
    if params.get("monthly_backfill_bucketed_output"):
        output_root = Path(str(context.metadata["output_root"]))
        references: list[str] = []
        bucket_run_dirs: list[str] = []
        bucket_counts: dict[str, int] = {}
        for month in sorted({_event_month(row) for row in rows}):
            month_rows = [row for row in rows if _event_month(row) == month]
            month_run_dir = output_root / month / "runs" / str(context.metadata["run_id"])
            cleaned_dir = month_run_dir / "cleaned"
            saved_dir = month_run_dir / "saved"
            atomic_write_json(
                month_run_dir / "request_manifest.json",
                {
                    "feed": FEED,
                    "source_request_manifest": str((context.run_dir / "request_manifest.json").resolve()),
                    "month": month,
                    "row_count": len(month_rows),
                    "persistence": "monthly bucket copied from one bounded recent Trading Economics refresh",
                },
            )
            atomic_write_text(cleaned_dir / "trading_economics_calendar_event.jsonl", "".join(json.dumps(sanitize_value(row), sort_keys=True) + "\n" for row in month_rows))
            atomic_write_json(cleaned_dir / "schema.json", {"trading_economics_calendar_event": FIELDS, "row_count": len(month_rows)})
            buffer = StringIO()
            writer = csv.DictWriter(buffer, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(month_rows)
            saved_path = saved_dir / "trading_economics_calendar_event.csv"
            atomic_write_text(saved_path, buffer.getvalue())
            references.append(str(saved_path))
            references.append(str(cleaned_dir / "trading_economics_calendar_event.jsonl"))
            bucket_run_dirs.append(str(month_run_dir))
            bucket_counts[month] = len(month_rows)
        return StepResult(
            "succeeded",
            references,
            dict(clean_result.row_counts),
            details={
                "format": "csv",
                "columns": FIELDS,
                "monthly_backfill_bucketed_output": True,
                "monthly_bucket_run_dirs": bucket_run_dirs,
                "monthly_bucket_row_counts": bucket_counts,
            },
        )
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / "trading_economics_calendar_event.csv"
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_text(path, buffer.getvalue())
    return StepResult("succeeded", [str(path)], dict(clean_result.row_counts), details={"format": "csv", "columns": FIELDS})


def write_receipt(context: FeedContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: Exception | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "feed": FEED, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": str(context.metadata["run_id"]), "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != entry["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "feed": FEED})
    write_receipt_bundle(context.receipt_path, context.run_dir, existing)
    if save_result is not None:
        for bucket_run_dir in save_result.details.get("monthly_bucket_run_dirs", []):
            bucket_run_path = Path(str(bucket_run_dir))
            write_receipt_bundle(bucket_run_path.parents[1] / "completion_receipt.json", bucket_run_path, existing)
    warnings = []
    for step in (fetch_result, clean_result, save_result):
        if step:
            warnings.extend(step.warnings)
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, warnings=warnings, details={"run_id": entry["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, fetched = fetch(context)
        clean_result = clean(context, fetched)
        save_result = save(context, clean_result)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except Exception as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
