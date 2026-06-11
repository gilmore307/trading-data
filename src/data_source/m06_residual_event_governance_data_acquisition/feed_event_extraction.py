"""Canonical event extraction from reviewed feed rows.

This module intentionally performs no provider calls. It converts SQL-retained
feed rows, and TE-exception local artifacts, into the compact
``m06_residual_event_governance_data_acquisition`` overview contract used by the
M06 event-risk governor. Raw article/filing/calendar detail remains behind
references.
"""

from __future__ import annotations

import csv
import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from storage.sql import PostgresSqlTableReader, SqlTableReader


class FeedEventExtractionError(ValueError):
    """Raised when a reviewed feed artifact cannot be normalized."""


SQL_INPUT_FIELDS_BY_KIND = {
    "alpaca_news": ["id", "timeline_headline", "created_at", "updated_at", "symbols", "summary", "event_link_url"],
    "gdelt_news": ["article_id", "seen_at", "source_domain", "event_link_url", "title", "source_theme_tags", "organizations", "tone", "impact_scope", "scope_type", "sector_type", "symbol"],
    "release_calendar": ["event_id", "calendar_source", "event_name", "release_time", "event_date", "timezone", "source_url", "raw_summary", "symbol"],
    "sec_company_financials": ["cik", "entity_name", "taxonomy", "tag", "label", "description", "unit", "fy", "fp", "form", "filed", "frame", "end", "value", "accession_number", "symbol"],
}

SQL_INPUT_KIND_BY_TABLE = {
    "feed_03_alpaca_news": "alpaca_news",
    "feed_05_gdelt_article": "gdelt_news",
    "feed_08_sec_company_fact": "sec_company_financials",
    "feed_12_release_calendar": "release_calendar",
}


def _as_list(value: Any) -> list[str]:
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip().strip("'\"") for item in parsed if str(item).strip().strip("'\"")]
    if ";" in text:
        return [item.strip() for item in text.split(";") if item.strip()]
    if "," in text:
        return [item.strip().strip("'\"[]") for item in text.split(",") if item.strip().strip("'\"[]")]
    return [text.strip("'\"[]")]


def _artifact_fetched_at(path: Path) -> str:
    for parent in [path.parent, *path.parents]:
        manifest = parent / "request_manifest.json"
        if manifest.exists():
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            fetched = str(payload.get("fetched_at_utc") or "").strip()
            if fetched:
                return fetched
    return ""


def _parse_dt(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FeedEventExtractionError(f"feed artifact does not exist: {path}")
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, Mapping):
                rows.append({str(key): "" if value is None else str(value) for key, value in payload.items()})
        return rows
    with path.open(newline="", encoding="utf-8") as handle:
        return [{str(key): str(value or "") for key, value in row.items()} for row in csv.DictReader(handle)]


def _reference(path: Path | str, row: Mapping[str, str], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return str(path)


def _first(row: Mapping[str, str], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _date_to_event_time(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return f"{text}T00:00:00-05:00"
    # Validate enough to catch obviously unusable values but preserve timezone text
    # for the canonical source cleaner to convert to ET.
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return text


def _base_event(
    *,
    artifact_path: Path | str,
    event_time: str,
    available_time: str | None,
    information_role_type: str,
    event_category_type: str,
    scope_type: str,
    title: str,
    summary: str,
    source_name: str,
    reference_type: str,
    reference: str,
    symbol: str | None = None,
    sector_type: str | None = None,
    source_priority: str | None = None,
    coverage_reason: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "event_time": event_time,
        "available_time": available_time or event_time,
        "information_role_type": information_role_type,
        "event_category_type": event_category_type,
        "scope_type": scope_type,
        "symbol": (symbol or "").upper() or None,
        "sector_type": sector_type or None,
        "title": title,
        "summary": summary,
        "source_name": source_name,
        "reference_type": reference_type,
        "reference": reference,
        "source_artifact_path": str(artifact_path),
        "dedup_status": "canonical",
        "coverage_reason": coverage_reason or "canonical_event_from_reviewed_feed_artifact",
    }
    if source_priority:
        row["source_priority"] = source_priority
    return row


def _alpaca_news_events(path: Path | str, rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        created_at = _first(row, "created_at", "updated_at")
        title = _first(row, "timeline_headline", "headline", "title")
        if not created_at or not title:
            continue
        symbols = _as_list(row.get("symbols")) or [""]
        for symbol in symbols:
            events.append(
                _base_event(
                    artifact_path=path,
                    event_time=created_at,
                    available_time=_first(row, "updated_at", "created_at"),
                    information_role_type="lagging_evidence",
                    event_category_type="symbol_news",
                    scope_type="symbol" if symbol else "macro",
                    symbol=symbol or None,
                    title=title,
                    summary=_first(row, "summary") or title,
                    source_name="03_feed_alpaca_news",
                    reference_type="web_url" if _first(row, "event_link_url") else "source_reference",
                    reference=_reference(path, row, "event_link_url", "id"),
                    source_priority="verified_news",
                    coverage_reason="canonical_symbol_news_from_alpaca_feed",
                )
            )
    return events


def _gdelt_news_events(path: Path | str, rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        seen_at = _first(row, "seen_at", "gdelt_date")
        if not seen_at:
            continue
        title = _first(row, "title") or _first(row, "source_theme_tags") or "GDELT market-relevant news article"
        scope = str(row.get("scope_type") or row.get("impact_scope") or "").lower()
        sector = _first(row, "sector_type")
        symbol = _first(row, "symbol")
        if symbol:
            category, scope_type = "symbol_news", "symbol"
        elif sector or "sector" in scope or "industry" in scope:
            category, scope_type = "sector_news", "sector"
        else:
            category, scope_type = "macro_news", "macro"
        source_domain = _first(row, "source_domain")
        summary_parts = [part for part in [source_domain, _first(row, "source_theme_tags"), _first(row, "organizations"), _first(row, "tone")] if part]
        events.append(
            _base_event(
                artifact_path=path,
                event_time=seen_at,
                available_time=seen_at,
                information_role_type="lagging_evidence",
                event_category_type=category,
                scope_type=scope_type,
                symbol=symbol or None,
                sector_type=sector or None,
                title=title,
                summary=" | ".join(summary_parts) or title,
                source_name="05_feed_gdelt_news",
                reference_type="web_url" if _first(row, "event_link_url") else "source_reference",
                reference=_reference(path, row, "event_link_url", "article_id"),
                source_priority="broad_news",
                coverage_reason="canonical_news_context_from_gdelt_feed",
            )
        )
    return events


def _release_calendar_events(path: Path | str, rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    """Normalize reviewed calendar-discovery artifacts into event shells.

    Earnings calendar rows are scheduling shells only. They establish a visible
    catalyst clock but intentionally do not carry result, beat/miss, guidance,
    or post-release interpretation fields.
    """

    events: list[dict[str, Any]] = []
    for row in rows:
        calendar_source = _first(row, "calendar_source")
        release_time = _first(row, "release_time", "event_time")
        event_name = _first(row, "event_name", "event", "title")
        if not calendar_source or not release_time or not event_name:
            continue
        source_url = _first(row, "source_url")
        raw_summary = _first(row, "raw_summary")
        symbol = ""
        if calendar_source == "nasdaq_earnings_calendar" and " earnings release" in event_name.lower():
            symbol = event_name.split(" ", 1)[0].strip().upper()
        category = "earnings_guidance" if calendar_source == "nasdaq_earnings_calendar" else "macro_data"
        summary_parts = [
            "event_phase=scheduled_shell" if category == "earnings_guidance" else "event_phase=scheduled_release",
            "lifecycle_class=scheduled_known_outcome_later" if category == "earnings_guidance" else "lifecycle_class=scheduled_release",
            "result_fields=not_available_from_calendar_shell" if category == "earnings_guidance" else "result_fields=calendar_schedule_only",
        ]
        if raw_summary:
            summary_parts.append(f"raw_summary={raw_summary}")
        events.append(
            _base_event(
                artifact_path=path,
                event_time=release_time,
                available_time=release_time,
                information_role_type="prior_signal",
                event_category_type=category,
                scope_type="symbol" if symbol else "macro",
                symbol=symbol or None,
                title=event_name,
                summary="; ".join(summary_parts),
                source_name=calendar_source,
                reference_type="web_url" if source_url else "source_reference",
                reference=_reference(path, row, "source_url", "event_id"),
                source_priority="approved_calendar" if calendar_source == "nasdaq_earnings_calendar" else "official_data_release",
                coverage_reason="earnings_guidance_scheduled_shell_from_approved_calendar" if calendar_source == "nasdaq_earnings_calendar" else "canonical_scheduled_release_from_calendar_artifact",
            )
        )
    return events


def _sec_group_key(path: Path | str, row: Mapping[str, str]) -> tuple[str, str, str, str]:
    accession = _first(row, "accession_number")
    if accession:
        return ("accession", accession, _first(row, "symbol"), _first(row, "cik"))
    return (
        str(path),
        _first(row, "cik"),
        _first(row, "filed", "filing_date", "end", "report_date"),
        _first(row, "form", "frame"),
    )


def _sec_events(path: Path | str, rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, str]]] = {}
    for row in rows:
        grouped.setdefault(_sec_group_key(path, row), []).append(row)
    for group_rows in grouped.values():
        row = group_rows[0]
        accession = _first(row, "accession_number")
        filed = _first(row, "filing_date", "filed")
        event_time = _date_to_event_time(filed or _first(row, "end", "report_date"))
        if not event_time:
            continue
        company = _first(row, "company_name", "entity_name", "loc") or _first(row, "cik") or "SEC company"
        form = _first(row, "form")
        tags = sorted({_first(item, "tag", "label") for item in group_rows if _first(item, "tag", "label")})
        tag = tags[0] if len(tags) == 1 else f"{len(tags)} financial facts" if tags else ""
        title_bits = [company, form or "SEC filing"]
        if tag:
            title_bits.append(tag)
        if _first(row, "fy") or _first(row, "fp"):
            title_bits.append(" ".join(part for part in [_first(row, "fy"), _first(row, "fp")] if part))
        summary_bits = []
        for key in ("report_date", "end", "taxonomy", "tag", "label", "unit", "value", "primary_document", "primary_doc_description"):
            value = _first(row, key)
            if value:
                summary_bits.append(f"{key}={value}")
        if len(group_rows) > 1:
            summary_bits.append(f"grouped_rows={len(group_rows)}")
            if tags:
                summary_bits.append("tags=" + ",".join(tags[:12]))
        form_upper = form.upper()
        is_earnings_result = form_upper in {"10-Q", "10-K"} or (
            form_upper == "8-K"
            and any("earning" in tag.lower() or "revenue" in tag.lower() or "income" in tag.lower() for tag in tags)
        )
        if is_earnings_result:
            summary_bits.extend(
                [
                    "event_phase=release_result",
                    "event_family=earnings_guidance_event_family",
                    "result_source_type=sec_edgar",
                    "lifecycle_class=scheduled_known_outcome_later",
                ]
            )
        events.append(
            _base_event(
                artifact_path=path,
                event_time=event_time,
                available_time=_date_to_event_time(filed) or event_time,
                information_role_type="prior_signal",
                event_category_type="earnings_guidance" if is_earnings_result else "sec_filing",
                scope_type="symbol",
                symbol=_first(row, "symbol") or None,
                title=" ".join(title_bits),
                summary="; ".join(summary_bits) or "SEC filing/financial disclosure row",
                source_name="08_feed_sec_company_financials",
                reference_type="sec_file_path" if accession else "source_reference",
                reference=accession or str(path),
                source_priority="official_disclosure",
                coverage_reason="earnings_guidance_result_artifact_from_sec_feed" if is_earnings_result else "canonical_sec_event_from_company_financials_feed",
            )
        )
    return events


def _detect_artifact_kind(path: Path, rows: Sequence[Mapping[str, str]]) -> str:
    name = path.name.lower()
    columns = set(rows[0].keys()) if rows else set()
    if "equity_news" in name or {"timeline_headline", "created_at", "symbols"}.issubset(columns):
        return "alpaca_news"
    if "gdelt_article" in name or "article_id" in columns and "source_theme_tags" in columns:
        return "gdelt_news"
    if "release_calendar" in name or {"calendar_source", "event_name", "release_time"}.issubset(columns):
        return "release_calendar"
    if name.startswith("sec_") or "accession_number" in columns or {"cik", "taxonomy", "tag"}.issubset(columns):
        return "sec_company_financials"
    raise FeedEventExtractionError(f"unsupported event feed artifact shape: {path}")


def _string_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [{str(key): "" if value is None else str(value) for key, value in row.items()} for row in rows]


def _events_for_kind(kind: str, reference: Path | str, rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    if kind == "alpaca_news":
        return _alpaca_news_events(reference, rows)
    if kind == "gdelt_news":
        return _gdelt_news_events(reference, rows)
    if kind == "release_calendar":
        return _release_calendar_events(reference, rows)
    if kind == "sec_company_financials":
        return _sec_events(reference, rows)
    raise FeedEventExtractionError(f"unsupported event SQL input kind: {kind}")


def extract_events_from_artifact_paths(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """Extract canonical M06 event-risk rows from local feed artifacts.

    This remains for TE-exception/local reviewed artifacts. Current non-TE feed
    outputs should prefer ``extract_events_from_sql_inputs``.
    """

    events: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        rows = _read_rows(path)
        if not rows:
            continue
        kind = _detect_artifact_kind(path, rows)
        events.extend(_events_for_kind(kind, path, rows))
    return events


def extract_events_from_sql_inputs(inputs: Iterable[Mapping[str, Any]], *, sql_reader: SqlTableReader | None = None) -> list[dict[str, Any]]:
    """Extract canonical M06 event-risk rows from SQL-retained feed tables."""

    reader = sql_reader or PostgresSqlTableReader.from_config({})
    events: list[dict[str, Any]] = []
    for item in inputs:
        table = str(item.get("table") or "").strip()
        if not table:
            raise FeedEventExtractionError("event_sql_inputs entries require table")
        kind = str(item.get("kind") or item.get("data_kind") or SQL_INPUT_KIND_BY_TABLE.get(table) or "").strip()
        if not kind:
            raise FeedEventExtractionError(f"event_sql_inputs entry for {table!r} requires kind")
        columns = [str(column) for column in item.get("columns") or SQL_INPUT_FIELDS_BY_KIND.get(kind) or []]
        if not columns:
            raise FeedEventExtractionError(f"no SQL columns registered for event input kind {kind!r}")
        where_equals = item.get("where_equals") if isinstance(item.get("where_equals"), Mapping) else None
        where_in = item.get("where_in") if isinstance(item.get("where_in"), Mapping) else None
        order_by = [str(column) for column in item.get("order_by") or []] or None
        rows = _string_rows(
            reader.read_rows(
                table=table,
                columns=columns,
                where_equals=where_equals,
                where_in=where_in,
                time_column=str(item.get("time_column") or "").strip() or None,
                start=item.get("start"),
                end=item.get("end"),
                order_by=order_by,
            )
        )
        if not rows:
            continue
        reference = f"sql://trading_data/{table}"
        events.extend(_events_for_kind(kind, reference, rows))
    return events


__all__ = ["FeedEventExtractionError", "extract_events_from_artifact_paths", "extract_events_from_sql_inputs"]
