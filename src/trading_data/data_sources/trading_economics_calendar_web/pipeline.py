"""Trading Economics visible calendar-page interface bundle.

This bundle intentionally handles only normal web-page-visible calendar rows. It
must not call Trading Economics API or download/export endpoints. Bulk historical
collection is out of scope until model needs and subscription constraints are
accepted explicitly.
"""

from __future__ import annotations

import csv
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from trading_data.source_availability.sanitize import sanitize_value

BUNDLE = "trading_economics_calendar_web"
SOURCE_URL = "https://tradingeconomics.com/united-states/calendar"
DEFAULT_COOKIE_JAR = Path("/root/secrets/tradingeconomics-cookies.txt")
FIELDS = [
    "event_time_et",
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
class BundleContext:
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


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise TradingEconomicsCalendarError(f"task_key.bundle must be {BUNDLE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


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


def _cookie_header(cookie_jar: Path = DEFAULT_COOKIE_JAR) -> str:
    if not cookie_jar.exists():
        return ""
    cookies: list[str] = []
    for line in cookie_jar.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies.append(f"{parts[5]}={parts[6]}")
    return "; ".join(cookies)


def _build_url(params: Mapping[str, Any]) -> str:
    start, end = _window(params)
    query = urllib.parse.urlencode({"importance": str(params.get("importance") or "3"), "start": start.isoformat(), "end": end.isoformat()})
    return SOURCE_URL + "?" + query


def fetch(context: BundleContext) -> tuple[StepResult, FetchedPage]:
    params = dict(context.task_key.get("params") or {})
    source_url = str(params.get("source_url") or _build_url(params))
    html_path = params.get("html_path")
    if html_path:
        page = Path(str(html_path)).read_text(encoding="utf-8")
        fetched = FetchedPage(page, source_url, _now_utc())
    elif params.get("html"):
        fetched = FetchedPage(str(params["html"]), source_url, _now_utc())
    elif params.get("allow_live_fetch"):
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml",
        }
        cookie_header = _cookie_header()
        if cookie_header:
            headers["Cookie"] = cookie_header
        request = urllib.request.Request(source_url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=int(params.get("timeout_seconds", 30))) as response:
                fetched = FetchedPage(response.read().decode("utf-8", errors="replace"), source_url, _now_utc())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TradingEconomicsCalendarError(f"visible page fetch failed: {exc}") from exc
    else:
        raise TradingEconomicsCalendarError("provide params.html_path/html, or set allow_live_fetch=true for a bounded visible-page fetch")
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": "trading_economics_calendar_web",
        "source_url": source_url,
        "country": str(params.get("country") or "United States"),
        "importance": str(params.get("importance") or "3"),
        "fetched_at_utc": fetched.fetched_at_utc,
        "persistence": "final CSV only; raw page not persisted by default",
        "boundary": "visible web page only; no API or download/export endpoint",
    }
    path = context.run_dir / "request_manifest.json"
    path.write_text(json.dumps(sanitize_value(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "date": "event_time_et",
        "time": "event_time_et",
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


def parse_calendar_rows(html_text: str, *, source_url: str, default_country: str, default_importance: str) -> list[dict[str, str]]:
    rows = _table_rows(html_text)
    if not rows:
        return []
    header_i = next((i for i, row in enumerate(rows) if {"actual", "previous"}.intersection({cell.lower() for cell in row})), -1)
    if header_i < 0:
        return []
    index = _header_index(rows[header_i])
    parsed: list[dict[str, str]] = []
    for row in rows[header_i + 1 :]:
        if len(row) < 4:
            continue
        def at(name: str) -> str:
            idx = index.get(name)
            return row[idx] if idx is not None and idx < len(row) else ""
        event = at("event") or (row[2] if len(row) > 2 else "")
        if not event or event.lower() in {"event", "calendar"}:
            continue
        parsed.append({
            "event_time_et": at("event_time_et") or row[0],
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
            "source_url": source_url,
        })
    return parsed


def clean(context: BundleContext, fetched: FetchedPage) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    rows = parse_calendar_rows(fetched.html_text, source_url=fetched.source_url, default_country=str(params.get("country") or "United States"), default_importance=str(params.get("importance") or "3"))
    if not rows:
        raise TradingEconomicsCalendarError("Trading Economics page produced zero parseable calendar rows")
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    path = context.cleaned_dir / "trading_economics_calendar_event.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_value(row), sort_keys=True) + "\n")
    schema = context.cleaned_dir / "schema.json"
    schema.write_text(json.dumps({"trading_economics_calendar_event": FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path), str(schema)], {"trading_economics_calendar_event": len(rows)}, details={"columns": FIELDS})


def save(context: BundleContext, clean_result: StepResult) -> StepResult:
    rows = [json.loads(line) for line in (context.cleaned_dir / "trading_economics_calendar_event.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / "trading_economics_calendar_event.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return StepResult("succeeded", [str(path)], dict(clean_result.row_counts), details={"format": "csv", "columns": FIELDS})


def write_receipt(context: BundleContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: BaseException | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "bundle": BUNDLE, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": str(context.metadata["run_id"]), "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != entry["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "bundle": BUNDLE})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": entry["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, fetched = fetch(context)
        clean_result = clean(context, fetched)
        save_result = save(context, clean_result)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
