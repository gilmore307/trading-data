"""Unified calendar observation source layer.

Calendar observations are source/scheduling evidence. They do not enter the
Layer 10 event pool until Layer 10 explicitly promotes a relevant observation
with point-in-time evidence.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from data_runtime.temporal_explorer import build_market_session_rows

ET = ZoneInfo("America/New_York")

CALENDAR_OBSERVATION_FIELDS = [
    "observation_id",
    "observation_type",
    "calendar_source",
    "event_name",
    "calendar_date",
    "observation_time",
    "timezone",
    "event_window_start",
    "event_window_end",
    "scope_type",
    "symbol",
    "venue",
    "event_phase",
    "lifecycle_class",
    "source_priority",
    "certainty_status",
    "result_status",
    "source_ref",
    "payload_json",
]


@dataclass(frozen=True)
class CalendarObservation:
    observation_id: str
    observation_type: str
    calendar_source: str
    event_name: str
    calendar_date: str
    observation_time: str
    timezone: str
    event_window_start: str = ""
    event_window_end: str = ""
    scope_type: str = "market"
    symbol: str = ""
    venue: str = ""
    event_phase: str = "scheduled_shell"
    lifecycle_class: str = "scheduled_known_outcome_later"
    source_priority: str = "approved_calendar"
    certainty_status: str = "confirmed"
    result_status: str = "not_result_source"
    source_ref: str = ""
    payload_json: str = "{}"

    def row(self) -> dict[str, str]:
        return {field: str(asdict(self).get(field, "")) for field in CALENDAR_OBSERVATION_FIELDS}


def _stable_id(*parts: Any) -> str:
    digest = hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"calobs_{digest}"


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


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


def _iso(value: datetime | None) -> str:
    return "" if value is None else value.isoformat()


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _iter_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict):
                yield payload


def build_market_session_observations(
    start_date: date | str,
    end_date_exclusive: date | str,
    *,
    venues: Sequence[str] = ("NYSE", "NASDAQ", "CRYPTO_24_7"),
) -> list[CalendarObservation]:
    observations: list[CalendarObservation] = []
    for row in build_market_session_rows(start_date, end_date_exclusive, venues=venues):
        calendar_date = str(row["calendar_date"])
        venue = str(row["venue"])
        event_name = f"{venue} {row['session_type']} session"
        observations.append(
            CalendarObservation(
                observation_id=_stable_id("market_session", venue, calendar_date),
                observation_type="market_session",
                calendar_source="deterministic_market_session_calendar",
                event_name=event_name,
                calendar_date=calendar_date,
                observation_time=_iso(row.get("open_time") or datetime.combine(row["calendar_date"], time.min, UTC)),
                timezone=str(row["timezone"]),
                event_window_start=_iso(row.get("open_time")),
                event_window_end=_iso(row.get("close_time")),
                scope_type="market",
                venue=venue,
                event_phase="session_window",
                lifecycle_class="scheduled_market_structure",
                source_priority=str(row["source_priority"]),
                certainty_status="inferred_rule" if row["source_priority"] in {"inferred_rule", "deterministic_rule"} else "confirmed",
                source_ref=str(row["source_ref"]),
                payload_json=_json(row),
            )
        )
    return observations


def _third_friday(year: int, month: int) -> date:
    day = date(year, month, 1)
    while day.weekday() != 4:
        day += timedelta(days=1)
    return day + timedelta(days=14)


def _fridays(start: date, end: date) -> Iterable[date]:
    day = start
    while day.weekday() != 4:
        day += timedelta(days=1)
    while day < end:
        yield day
        day += timedelta(days=7)


def build_option_expiry_observations(start_date: date | str, end_date_exclusive: date | str) -> list[CalendarObservation]:
    start = _coerce_date(start_date)
    end = _coerce_date(end_date_exclusive)
    observations: list[CalendarObservation] = []
    for day in _fridays(start, end):
        monthly = day == _third_friday(day.year, day.month)
        triple_witching = monthly and day.month in {3, 6, 9, 12}
        if triple_witching:
            observation_type = "triple_witching"
            event_name = "US equity triple witching"
        elif monthly:
            observation_type = "monthly_option_expiry"
            event_name = "US equity monthly option expiry"
        else:
            observation_type = "weekly_option_expiry"
            event_name = "US equity weekly option expiry"
        start_at = datetime.combine(day, time(9, 30), ET)
        end_at = datetime.combine(day, time(16, 0), ET)
        payload = {
            "monthly_option_expiry": monthly,
            "triple_witching": triple_witching,
            "derivation": "friday_expiry_rule",
        }
        observations.append(
            CalendarObservation(
                observation_id=_stable_id(observation_type, day.isoformat()),
                observation_type=observation_type,
                calendar_source="deterministic_option_expiry_calendar",
                event_name=event_name,
                calendar_date=day.isoformat(),
                observation_time=start_at.isoformat(),
                timezone="America/New_York",
                event_window_start=start_at.isoformat(),
                event_window_end=end_at.isoformat(),
                scope_type="market",
                event_phase="scheduled_market_structure",
                lifecycle_class="scheduled_market_structure",
                source_priority="deterministic_rule",
                certainty_status="inferred_rule",
                source_ref="trading_data.data_runtime.calendar_observation",
                payload_json=_json(payload),
            )
        )
    return observations


def release_calendar_observations(paths: Sequence[Path | str]) -> list[CalendarObservation]:
    observations: list[CalendarObservation] = []
    for path_value in paths:
        path = Path(path_value)
        for row in _iter_csv(path):
            calendar_source = str(row.get("calendar_source") or "")
            event_name = str(row.get("event_name") or "")
            release_time = _parse_datetime(row.get("release_time"))
            if not calendar_source or not event_name or release_time is None:
                continue
            symbol = ""
            scope_type = "macro"
            observation_type = "release_calendar"
            lifecycle_class = "scheduled_known_outcome_later"
            if calendar_source == "nasdaq_earnings_calendar":
                observation_type = "earnings_calendar"
                scope_type = "symbol"
                symbol = event_name.split(" ", 1)[0].strip().upper()
            observations.append(
                CalendarObservation(
                    observation_id=_stable_id(calendar_source, event_name, release_time.isoformat(), path),
                    observation_type=observation_type,
                    calendar_source=calendar_source,
                    event_name=event_name,
                    calendar_date=str(row.get("event_date") or release_time.date().isoformat()),
                    observation_time=release_time.isoformat(),
                    timezone=str(row.get("timezone") or "America/New_York"),
                    event_window_start=release_time.isoformat(),
                    event_window_end=release_time.isoformat(),
                    scope_type=scope_type,
                    symbol=symbol,
                    event_phase="scheduled_shell",
                    lifecycle_class=lifecycle_class,
                    source_priority="approved_calendar" if calendar_source == "nasdaq_earnings_calendar" else "official_data_release",
                    certainty_status="tentative" if calendar_source == "nasdaq_earnings_calendar" else "confirmed",
                    result_status="result_fields_not_available",
                    source_ref=str(row.get("source_url") or path),
                    payload_json=_json(row),
                )
            )
    return observations


def trading_economics_observations(paths: Sequence[Path | str]) -> list[CalendarObservation]:
    observations: list[CalendarObservation] = []
    for path_value in paths:
        path = Path(path_value)
        if path.suffix == ".csv":
            rows: Iterable[Mapping[str, Any]] = _iter_csv(path)
        else:
            rows = _iter_jsonl(path)
        for row in rows:
            event_name = str(row.get("event") or "")
            event_time = _parse_datetime(row.get("event_time"))
            if not event_name or event_time is None:
                continue
            observations.append(
                CalendarObservation(
                    observation_id=_stable_id("trading_economics_calendar_web", event_name, event_time.isoformat(), row.get("reference"), path),
                    observation_type="macro_release_calendar",
                    calendar_source="trading_economics_calendar_web",
                    event_name=event_name,
                    calendar_date=event_time.date().isoformat(),
                    observation_time=event_time.isoformat(),
                    timezone="America/New_York",
                    event_window_start=event_time.isoformat(),
                    event_window_end=event_time.isoformat(),
                    scope_type="macro",
                    event_phase="scheduled_release",
                    lifecycle_class="scheduled_recurring_data_release",
                    source_priority="approved_calendar",
                    certainty_status="confirmed",
                    result_status="calendar_value_fields_may_be_present",
                    source_ref=str(path),
                    payload_json=_json(row),
                )
            )
    return observations


def sort_observations(observations: Iterable[CalendarObservation]) -> list[CalendarObservation]:
    return sorted(observations, key=lambda item: (item.calendar_date, item.observation_time, item.observation_type, item.event_name, item.symbol))


def write_observations(observations: Sequence[CalendarObservation], output_dir: Path | str) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = [observation.row() for observation in sort_observations(observations)]
    csv_path = output / "calendar_observation.csv"
    jsonl_path = output / "calendar_observation.jsonl"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CALENDAR_OBSERVATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    schema_path = output / "schema.json"
    schema_path.write_text(json.dumps({"calendar_observation": CALENDAR_OBSERVATION_FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "contract_type": "calendar_observation_build_receipt",
        "row_count": len(rows),
        "outputs": [str(csv_path), str(jsonl_path), str(schema_path)],
        "source_role": "calendar_observations_are_source_shells_not_layer_10_event_pool_rows",
    }


__all__ = [
    "CALENDAR_OBSERVATION_FIELDS",
    "CalendarObservation",
    "build_market_session_observations",
    "build_option_expiry_observations",
    "release_calendar_observations",
    "trading_economics_observations",
    "sort_observations",
    "write_observations",
]
