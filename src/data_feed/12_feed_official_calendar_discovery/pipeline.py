"""Official calendar discovery acquisition feed.

The feed produces reviewed calendar artifacts that the unified
``calendar_observation`` source-shell builder can consume. It does not promote
events into Layer 10.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time
from html import unescape
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from data_runtime.config import resolve_output_root
from data_runtime.io import write_receipt_bundle
from data_runtime.provider_policy import require_provider_execution_allowed
from data_feed.sql_only import sql_reference, sql_rows, write_schema, write_table
from feed_availability.http import HttpClient, HttpResult
from feed_availability.sanitize import sanitize_url, sanitize_value
from storage.sql import SqlTableWriter

FEED = "12_feed_official_calendar_discovery"
DEFAULT_TIMEOUT_SECONDS = 20
ET = ZoneInfo("America/New_York")

SUPPORTED_DATA_KINDS = {
    "nasdaq_earnings_calendar",
    "official_index_announcement",
    "official_exchange_calendar",
}
OUTPUT_BY_KIND = {
    "nasdaq_earnings_calendar": "release_calendar",
    "official_index_announcement": "index_calendar",
    "official_exchange_calendar": "official_exchange_calendar",
}
TABLE_BY_OUTPUT = {
    "release_calendar": "feed_12_release_calendar",
    "index_calendar": "feed_12_index_calendar",
    "official_exchange_calendar": "feed_12_official_exchange_calendar",
}
KEYS_BY_OUTPUT = {
    "release_calendar": ["calendar_source", "event_date", "release_time", "symbol", "event_name"],
    "index_calendar": ["calendar_source", "index_symbol", "event_type", "announcement_time", "event_name"],
    "official_exchange_calendar": ["venue", "calendar_date", "session_status"],
}
FIELD_ORDER = {
    "release_calendar": [
        "calendar_source",
        "event_name",
        "event_date",
        "release_time",
        "timezone",
        "source_url",
        "retrieved_time",
        "symbol",
        "company_name",
        "time_hint",
        "certainty_status",
    ],
    "index_calendar": [
        "calendar_source",
        "index_symbol",
        "event_type",
        "event_name",
        "announcement_time",
        "effective_time",
        "event_window_start",
        "event_window_end",
        "event_phase",
        "certainty_status",
        "result_status",
        "source_ref",
        "source_url",
        "retrieved_time",
        "source_text_sha256",
        "source_text_path",
    ],
    "official_exchange_calendar": [
        "venue",
        "calendar_date",
        "session_status",
        "open_time",
        "close_time",
        "holiday_name",
        "timezone",
        "source_ref",
        "retrieved_time",
    ],
}


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
class FetchedCalendarPayload:
    data_kind: str
    payload: Any
    source_url: str
    http_status: int | None
    retrieved_time: str
    source_format: str
    request: dict[str, Any]


@dataclass(frozen=True)
class CleanedPayload:
    output_kind: str
    rows: list[dict[str, Any]]


class OfficialCalendarDiscoveryError(ValueError):
    """Raised for invalid official calendar discovery tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise OfficialCalendarDiscoveryError(f"{FEED}.params.{key} is required")
    return value


def build_context(task_key: dict[str, Any], run_id: str) -> FeedContext:
    if task_key.get("feed") != FEED:
        raise OfficialCalendarDiscoveryError(f"task_key.feed must be {FEED}")
    output_root = resolve_output_root(task_key, default_task_id=f"{FEED}_task")
    run_dir = output_root / "runs" / run_id
    return FeedContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _json_response(result: HttpResult) -> Any:
    if result.status is None:
        raise OfficialCalendarDiscoveryError(f"request failed before HTTP response: {result.error_type}: {result.error_message}")
    if result.status < 200 or result.status >= 300:
        raise OfficialCalendarDiscoveryError(f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}")
    text = result.text()
    try:
        return result.json()
    except json.JSONDecodeError:
        return text


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _local_payload(params: Mapping[str, Any]) -> tuple[Any, str, str] | None:
    if params.get("csv_path"):
        path = Path(str(params["csv_path"]))
        return {"rows": _csv_rows(path)}, str(path), "csv"
    if params.get("json_path"):
        path = Path(str(params["json_path"]))
        return json.loads(path.read_text(encoding="utf-8")), str(path), "json"
    if params.get("json_text"):
        return json.loads(str(params["json_text"])), "inline_json_text", "json"
    if params.get("text_path"):
        path = Path(str(params["text_path"]))
        return path.read_text(encoding="utf-8"), str(path), "text"
    if params.get("source_text"):
        return str(params["source_text"]), str(params.get("source_url") or "inline_source_text"), "text"
    return None


def _default_url(data_kind: str, params: Mapping[str, Any]) -> str:
    if data_kind == "nasdaq_earnings_calendar":
        return str(params.get("source_url") or "https://api.nasdaq.com/api/calendar/earnings")
    if data_kind == "official_exchange_calendar":
        return str(params.get("source_url") or "https://www.nyse.com/trade/hours-calendars")
    return str(_required(params, "source_url"))


def fetch(context: FeedContext, *, client: HttpClient | None = None, client_is_fixture: bool = False) -> tuple[StepResult, FetchedCalendarPayload]:
    params = dict(context.task_key.get("params") or {})
    data_kind = str(params.get("data_kind") or "")
    if data_kind not in SUPPORTED_DATA_KINDS:
        raise OfficialCalendarDiscoveryError(f"unsupported data_kind {data_kind!r}; supported={sorted(SUPPORTED_DATA_KINDS)}")
    retrieved_time = _now_utc()
    local = _local_payload(params)
    if local is not None:
        payload, source_url, source_format = local
        fetched = FetchedCalendarPayload(data_kind, payload, source_url, None, retrieved_time, source_format, {"data_kind": data_kind, "source": "local_artifact"})
        context.run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {"source": source_url, "data_kind": data_kind, "fetched_at_utc": retrieved_time, "source_format": source_format, "raw_persistence": "input_artifact_referenced_not_copied"}
        manifest_path = context.run_dir / "request_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return StepResult("succeeded", [str(manifest_path)], {"raw_calendar_payloads": 1}, details=fetched.request), fetched

    if not client_is_fixture:
        require_provider_execution_allowed(context.task_key, provider=_provider_name(data_kind, params), endpoint_family="calendar_discovery", requested_requests=1)
    url = _default_url(data_kind, params)
    request_params: dict[str, str] | None = None
    if data_kind == "nasdaq_earnings_calendar":
        request_params = {"date": str(_required(params, "date"))}
    client = client or HttpClient(timeout_seconds=int(params.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)))
    headers = {
        "Accept": "application/json,text/html",
        "User-Agent": str(params.get("user_agent") or "trading-data official calendar discovery; contact configured by manager task"),
    }
    if "nasdaq.com" in url:
        headers["Referer"] = "https://www.nasdaq.com/market-activity/earnings"
    result = client.get(url, params=request_params, headers=headers)
    payload = _json_response(result)
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = context.run_dir / "request_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "endpoint": sanitize_url(result.url),
                "http_status": result.status,
                "request": sanitize_value({"data_kind": data_kind, "params": request_params or {}}),
                "fetched_at_utc": retrieved_time,
                "source_format": "json" if isinstance(payload, (Mapping, list)) else "text",
                "raw_persistence": "not_persisted_by_default",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    fetched = FetchedCalendarPayload(data_kind, payload, result.url, result.status, retrieved_time, "json" if isinstance(payload, (Mapping, list)) else "text", {"data_kind": data_kind, "source": "live_request"})
    return StepResult("succeeded", [str(manifest_path)], {"raw_calendar_payloads": 1}, details=fetched.request), fetched


def _provider_name(data_kind: str, params: Mapping[str, Any]) -> str:
    if data_kind == "nasdaq_earnings_calendar":
        return "nasdaq"
    if data_kind == "official_index_announcement":
        calendar_source = str(params.get("calendar_source") or params.get("source_provider") or "").lower()
        if "nasdaq" in calendar_source:
            return "nasdaq_global_indexes"
        return "sp_dow_jones_indices"
    return "official_exchange"


def _strip_html(value: Any) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def _symbols_filter(params: Mapping[str, Any]) -> set[str]:
    value = params.get("symbols") or params.get("symbol")
    if value in (None, ""):
        return set()
    if isinstance(value, str):
        items = value.replace(";", ",").split(",")
    else:
        items = list(value)
    return {str(item).strip().upper() for item in items if str(item).strip()}


def _extract_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, Mapping)]
    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, Mapping)]
    if isinstance(data, Mapping):
        for key in ("rows", "calendar", "earnings"):
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, Mapping)]
            if isinstance(value, Mapping) and isinstance(value.get("rows"), list):
                return [row for row in value["rows"] if isinstance(row, Mapping)]
    return []


def _coerce_date(value: Any, *, fallback: str | None = None) -> str:
    text = str(value or fallback or "").strip()
    if not text:
        raise OfficialCalendarDiscoveryError("calendar date is required")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise OfficialCalendarDiscoveryError(f"unsupported date value: {value!r}") from exc


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ET)
    return parsed


def _earnings_release_time(event_date: str, time_hint: Any) -> str:
    hint = _strip_html(time_hint).lower()
    if any(term in hint for term in ("before", "pre-market", "premarket", "bmo")):
        release = datetime.combine(date.fromisoformat(event_date), time(7, 0), ET)
    elif any(term in hint for term in ("after", "post-market", "postmarket", "amc")):
        release = datetime.combine(date.fromisoformat(event_date), time(16, 5), ET)
    elif any(term in hint for term in ("market open", "during")):
        release = datetime.combine(date.fromisoformat(event_date), time(12, 0), ET)
    else:
        release = datetime.combine(date.fromisoformat(event_date), time.min, ET)
    return release.isoformat()


def _normalize_nasdaq_earnings(fetched: FetchedCalendarPayload, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    symbol_filter = _symbols_filter(params)
    rows: list[dict[str, Any]] = []
    for row in _extract_rows(fetched.payload):
        symbol = _strip_html(row.get("symbol") or row.get("ticker") or row.get("Symbol")).upper()
        if symbol_filter and symbol not in symbol_filter:
            continue
        event_date = _coerce_date(row.get("reportDate") or row.get("date") or row.get("event_date"), fallback=str(params.get("date") or ""))
        company_name = _strip_html(row.get("name") or row.get("companyName") or row.get("company") or row.get("Company"))
        time_hint = _strip_html(row.get("time") or row.get("reportTime") or row.get("timeOfDay") or row.get("Time"))
        if not symbol and not company_name:
            continue
        rows.append(
            {
                "calendar_source": "nasdaq_earnings_calendar",
                "event_name": f"{symbol} earnings" if symbol else f"{company_name} earnings",
                "event_date": event_date,
                "release_time": str(row.get("release_time") or _earnings_release_time(event_date, time_hint)),
                "timezone": "America/New_York",
                "source_url": fetched.source_url,
                "retrieved_time": fetched.retrieved_time,
                "symbol": symbol,
                "company_name": company_name,
                "time_hint": time_hint,
                "certainty_status": "tentative",
            }
        )
    return rows


def _index_calendar_source(params: Mapping[str, Any]) -> str:
    explicit = str(params.get("calendar_source") or "").strip()
    if explicit:
        if explicit not in {"nasdaq_global_indexes_announcement", "sp_dow_jones_indices_announcement"}:
            raise OfficialCalendarDiscoveryError("index announcements must come from Nasdaq Global Indexes or S&P Dow Jones Indices")
        return explicit
    provider = str(params.get("source_provider") or "").lower()
    index_symbol = str(params.get("index_symbol") or "").upper()
    if "etf" in provider or index_symbol in {"QQQ", "SPY", "DIA"}:
        raise OfficialCalendarDiscoveryError("ETF issuer pages are outside the index calendar source route")
    if "nasdaq" in provider or index_symbol == "NDX":
        return "nasdaq_global_indexes_announcement"
    return "sp_dow_jones_indices_announcement"


def _normalize_index_announcement(fetched: FetchedCalendarPayload, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    calendar_source = _index_calendar_source(params)
    index_symbol = str(_required(params, "index_symbol")).upper()
    if index_symbol == "DJI":
        index_symbol = "DJIA"
    if index_symbol not in {"NDX", "SPX", "DJIA"}:
        raise OfficialCalendarDiscoveryError("index_symbol must be one of NDX, SPX, DJIA")
    if calendar_source == "nasdaq_global_indexes_announcement" and index_symbol != "NDX":
        raise OfficialCalendarDiscoveryError("Nasdaq Global Indexes announcement rows are accepted only for NDX")
    text = fetched.payload if isinstance(fetched.payload, str) else json.dumps(fetched.payload, sort_keys=True, default=str)
    text_sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    source_text_path = ""
    if text.strip():
        source_text_path = str(Path("source_text.txt"))
    announcement_time = _parse_datetime(params.get("announcement_time")) or datetime.fromisoformat(fetched.retrieved_time.replace("Z", "+00:00"))
    effective_time = _parse_datetime(params.get("effective_time"))
    return [
        {
            "calendar_source": calendar_source,
            "index_symbol": index_symbol,
            "event_type": str(params.get("event_type") or "index_constituent_change"),
            "event_name": str(params.get("event_name") or f"{index_symbol} official index announcement"),
            "announcement_time": announcement_time.isoformat(),
            "effective_time": "" if effective_time is None else effective_time.isoformat(),
            "event_window_start": str(params.get("event_window_start") or (effective_time.isoformat() if effective_time else "")),
            "event_window_end": str(params.get("event_window_end") or (effective_time.isoformat() if effective_time else "")),
            "event_phase": str(params.get("event_phase") or "announced_result"),
            "certainty_status": "confirmed",
            "result_status": "membership_result_available",
            "source_ref": str(params.get("source_ref") or params.get("source_url") or fetched.source_url),
            "source_url": str(params.get("source_url") or fetched.source_url),
            "retrieved_time": fetched.retrieved_time,
            "source_text_sha256": text_sha,
            "source_text_path": source_text_path,
        }
    ]


def _normalize_exchange_calendar(fetched: FetchedCalendarPayload, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(fetched.payload, str) and "nyse.com" in fetched.source_url:
        return _normalize_nyse_exchange_calendar_text(fetched, params)
    rows = _extract_rows(fetched.payload)
    if not rows:
        rows = [params]
    output: list[dict[str, Any]] = []
    for row in rows:
        venue = str(row.get("venue") or params.get("venue") or "").upper()
        status = str(row.get("session_status") or row.get("session_type") or params.get("session_status") or "").lower()
        if venue not in {"NYSE", "NASDAQ"} or status not in {"closed", "early_close", "regular"}:
            continue
        output.append(
            {
                "venue": venue,
                "calendar_date": _coerce_date(row.get("calendar_date") or row.get("date") or params.get("calendar_date")),
                "session_status": status,
                "open_time": str(row.get("open_time") or params.get("open_time") or ""),
                "close_time": str(row.get("close_time") or params.get("close_time") or ""),
                "holiday_name": str(row.get("holiday_name") or row.get("event_name") or params.get("holiday_name") or ""),
                "timezone": str(row.get("timezone") or params.get("timezone") or "America/New_York"),
                "source_ref": str(row.get("source_ref") or params.get("source_ref") or params.get("source_url") or fetched.source_url),
                "retrieved_time": fetched.retrieved_time,
            }
        )
    return output


def _normalize_nyse_exchange_calendar_text(fetched: FetchedCalendarPayload, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_text = str(fetched.payload or "")
    text = _strip_html(raw_text)
    if "All NYSE markets observe" not in text or "Holidays & Trading Hours" not in text:
        return []
    holiday_names = [
        "New Year’s Day",
        "Martin Luther King, Jr. Day",
        "Washington's Birthday",
        "Good Friday",
        "Memorial Day",
        "Juneteenth National Independence Day",
        "Independence Day",
        "Labor Day",
        "Thanksgiving Day",
        "Christmas Day",
    ]
    table_years, table_rows = _nyse_holiday_table(raw_text, holiday_names)
    if table_years:
        listed_years = table_years[:3]
    else:
        years = [int(year) for year in re.findall(r"\b20\d{2}\b", text)]
        listed_years = []
        for year in years:
            if year not in listed_years:
                listed_years.append(year)
        listed_years = [year for year in listed_years if 2020 <= year <= 2100][:3]
    output: list[dict[str, Any]] = []
    holiday_cells: dict[str, list[str]] = {}
    if table_rows:
        holiday_cells = table_rows
    else:
        line_segments = _nyse_holiday_line_segments(fetched.payload, holiday_names)
        holiday_cells = {holiday_name: [segment] for holiday_name, segment in line_segments.items()}
    for holiday_name, cells in holiday_cells.items():
        if table_rows:
            for year, cell in zip(listed_years, cells):
                match = re.search(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Z][a-z]+)\s+(\d{1,2})", cell)
                if not match:
                    continue
                month_name, day_text = match.groups()
                calendar_date = datetime.strptime(f"{month_name} {day_text} {year}", "%B %d %Y").date()
                output.extend(_exchange_rows_for_session(fetched, calendar_date, "closed", holiday_name))
            continue
        dates = re.findall(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Z][a-z]+)\s+(\d{1,2})", " ".join(cells))
        for year, (month_name, day_text) in zip(listed_years, dates):
            calendar_date = datetime.strptime(f"{month_name} {day_text} {year}", "%B %d %Y").date()
            output.extend(_exchange_rows_for_session(fetched, calendar_date, "closed", holiday_name))
    early_close_segments = [
        text[match.start() : match.start() + 360]
        for match in re.finditer(r"close early", text, flags=re.IGNORECASE)
    ]
    for sentence in early_close_segments:
        dates = re.findall(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(20\d{2})",
            sentence,
        )
        for month_name, day_text, year_text in dates:
            calendar_date = datetime.strptime(f"{month_name} {day_text} {year_text}", "%B %d %Y").date()
            if calendar_date.month == 11:
                holiday_name = "Day after Thanksgiving"
            elif calendar_date.month == 12 and calendar_date.day == 24:
                holiday_name = "Christmas Eve"
            elif calendar_date.month == 7:
                holiday_name = "Independence Day early close"
            else:
                holiday_name = "NYSE official early close"
            output.extend(_exchange_rows_for_session(fetched, calendar_date, "early_close", holiday_name))
    return _dedupe_exchange_rows(output)


def _nyse_holiday_table(payload: str, holiday_names: list[str]) -> tuple[list[int], dict[str, list[str]]]:
    years: list[int] = []
    rows: dict[str, list[str]] = {}
    for table_match in re.finditer(r"<table\b[^>]*>(.*?)</table>", payload, flags=re.IGNORECASE | re.DOTALL):
        table_html = table_match.group(1)
        if "Holiday" not in table_html or "New Year" not in table_html:
            continue
        for tr_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL):
            cells = [
                _strip_html(cell)
                for cell in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr_html, flags=re.IGNORECASE | re.DOTALL)
            ]
            cells = [cell for cell in cells if cell]
            if not cells:
                continue
            if cells[0] == "Holiday":
                years = [int(cell) for cell in cells[1:] if re.fullmatch(r"20\d{2}", cell)]
                continue
            holiday_name = cells[0]
            if holiday_name in holiday_names:
                rows[holiday_name] = cells[1:]
        if years and rows:
            return years, rows
    return years, rows


def _nyse_holiday_line_segments(payload: str, holiday_names: list[str]) -> dict[str, str]:
    segments: dict[str, str] = {}
    weekdays = "Monday|Tuesday|Wednesday|Thursday|Friday"
    for raw_line in payload.splitlines():
        line = _strip_html(raw_line)
        if not line:
            continue
        candidates: list[tuple[int, str, str]] = []
        for holiday_name in holiday_names:
            match = re.search(rf"{re.escape(holiday_name)}\s*(?:{weekdays}),", line)
            if match:
                candidates.append((match.start(), holiday_name, line[match.start() :]))
        if candidates:
            _start, holiday_name, segment = min(candidates)
            segments[holiday_name] = segment
    if segments:
        return segments
    text = _strip_html(payload)
    cursor = 0
    for index, holiday_name in enumerate(holiday_names):
        start = text.find(holiday_name, cursor)
        if start < 0:
            continue
        following = [text.find(next_name, start + len(holiday_name)) for next_name in holiday_names[index + 1 :]]
        following = [position for position in following if position >= 0]
        end = min(following) if following else len(text)
        cursor = end
        segments[holiday_name] = text[start:end]
    return segments


def _exchange_rows_for_session(
    fetched: FetchedCalendarPayload,
    calendar_date: date,
    session_status: str,
    holiday_name: str,
) -> list[dict[str, Any]]:
    open_time = ""
    close_time = ""
    if session_status == "early_close":
        open_time = datetime.combine(calendar_date, time(9, 30), ET).isoformat()
        close_time = datetime.combine(calendar_date, time(13, 0), ET).isoformat()
    return [
        {
            "venue": venue,
            "calendar_date": calendar_date.isoformat(),
            "session_status": session_status,
            "open_time": open_time,
            "close_time": close_time,
            "holiday_name": holiday_name,
            "timezone": "America/New_York",
            "source_ref": fetched.source_url,
            "retrieved_time": fetched.retrieved_time,
        }
        for venue in ("NYSE", "NASDAQ")
    ]


def _dedupe_exchange_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["venue"]), str(row["calendar_date"]), str(row["session_status"]))
        by_key[key] = row
    return [by_key[key] for key in sorted(by_key)]


def normalize_rows(fetched: FetchedCalendarPayload, *, params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    params = params or {}
    if fetched.data_kind == "nasdaq_earnings_calendar":
        return _normalize_nasdaq_earnings(fetched, params)
    if fetched.data_kind == "official_index_announcement":
        return _normalize_index_announcement(fetched, params)
    if fetched.data_kind == "official_exchange_calendar":
        return _normalize_exchange_calendar(fetched, params)
    raise AssertionError(fetched.data_kind)


def clean(context: FeedContext, fetched: FetchedCalendarPayload) -> tuple[StepResult, CleanedPayload]:
    params = dict(context.task_key.get("params") or {})
    output_kind = OUTPUT_BY_KIND[fetched.data_kind]
    rows = normalize_rows(fetched, params=params)
    if not rows:
        if fetched.data_kind != "nasdaq_earnings_calendar":
            raise OfficialCalendarDiscoveryError(f"{fetched.data_kind} response produced zero normalized rows")
        schema_path = write_schema(context.run_dir, output_kind, FIELD_ORDER[output_kind], row_count=0)
        return (
            StepResult(
                "succeeded",
                [str(schema_path)],
                {output_kind: 0},
                warnings=["nasdaq_earnings_calendar returned no normalized rows for the requested date and symbol filter"],
                details={"columns": FIELD_ORDER[output_kind], "format": "sql_ready_rows", "retention": "sql_only_no_jsonl_or_csv_payload", "empty_result": True},
            ),
            CleanedPayload(output_kind, []),
        )
    if fetched.data_kind == "official_index_announcement":
        text = fetched.payload if isinstance(fetched.payload, str) else json.dumps(fetched.payload, sort_keys=True, default=str)
        if text.strip():
            context.run_dir.mkdir(parents=True, exist_ok=True)
            text_path = context.run_dir / "source_text.txt"
            text_path.write_text(text, encoding="utf-8")
            for row in rows:
                row["source_text_path"] = str(text_path)
    schema_path = write_schema(context.run_dir, output_kind, FIELD_ORDER[output_kind], row_count=len(rows))
    return (
        StepResult("succeeded", [str(schema_path)], {output_kind: len(rows)}, details={"columns": FIELD_ORDER[output_kind], "format": "sql_ready_rows", "retention": "sql_only_no_jsonl_or_csv_payload"}),
        CleanedPayload(output_kind, sql_rows([sanitize_value(row) for row in rows], FIELD_ORDER[output_kind])),
    )


def save(context: FeedContext, clean_result: StepResult, payload: CleanedPayload, *, sql_writer: SqlTableWriter | None = None) -> StepResult:
    output_kind = next(iter(clean_result.row_counts))
    metadata = write_table(table=TABLE_BY_OUTPUT[output_kind], columns=FIELD_ORDER[output_kind], rows=payload.rows, key_columns=KEYS_BY_OUTPUT[output_kind], sql_writer=sql_writer)
    references = [sql_reference(metadata)]
    if output_kind == "index_calendar":
        references.extend(str(row["source_text_path"]) for row in payload.rows if row.get("source_text_path"))
    return StepResult("succeeded", references, dict(clean_result.row_counts), details={"format": "sql_table", "table": TABLE_BY_OUTPUT[output_kind], "columns": FIELD_ORDER[output_kind], "storage": metadata, "file_payload_deleted": True})


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
    entry = {
        "run_id": context.metadata["run_id"],
        "status": status,
        "started_at": context.metadata.get("started_at"),
        "completed_at": _now_utc(),
        "output_dir": str(context.run_dir),
        "outputs": outputs,
        "row_counts": row_counts,
        "source_role": "calendar_discovery_artifacts_are_source_shell_inputs_not_layer_10_event_pool_rows",
        "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None},
        "error": None if error is None else {"type": type(error).__name__, "message": str(error)},
    }
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != context.metadata["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "feed": FEED})
    write_receipt_bundle(context.receipt_path, context.run_dir, existing)
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": context.metadata["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None, client_is_fixture: bool = False, sql_writer: SqlTableWriter | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, fetched = fetch(context, client=client, client_is_fixture=client_is_fixture)
        clean_result, payload = clean(context, fetched)
        save_result = save(context, clean_result, payload, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except Exception as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
