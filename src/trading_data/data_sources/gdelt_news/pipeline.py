"""GDELT BigQuery-backed global news acquisition bundle.

This bundle acquires source article records from GDELT's public BigQuery tables.
It is a source-evidence layer for political/economic/technology/geopolitical
and broad-market event discovery. Event clustering/scoring happens later in the
unified event layer.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Mapping, Protocol

from trading_data.source_availability.sanitize import sanitize_value

BUNDLE = "gdelt_news"
ET = ZoneInfo("America/New_York")
DEFAULT_MAX_ROWS = 100
DEFAULT_FOCUS = "us_market"
DEFAULT_TOPIC_CATEGORIES = ("politics", "economy", "war", "technology")
TOPIC_CATEGORY_TERMS = {
    "politics": ("government", "congress", "white house", "election", "regulation", "policy", "tariff", "sanction", "supreme court", "federal reserve"),
    "economy": ("inflation", "cpi", "ppi", "jobs", "payrolls", "unemployment", "gdp", "recession", "consumer spending", "retail sales", "interest rates", "treasury yields"),
    "war": ("war", "military", "missile", "conflict", "invasion", "geopolitical", "defense", "terrorism", "ceasefire", "shipping route"),
    "technology": ("technology", "semiconductor", "chip", "artificial intelligence", "ai", "cybersecurity", "cloud", "export controls", "data center", "software"),
}
DEFAULT_US_MARKET_DOMAINS = (
    "apnews.com",
    "barrons.com",
    "bloomberg.com",
    "cnbc.com",
    "cnn.com",
    "finance.yahoo.com",
    "forbes.com",
    "fortune.com",
    "foxbusiness.com",
    "marketwatch.com",
    "nytimes.com",
    "politico.com",
    "reuters.com",
    "techcrunch.com",
    "thehill.com",
    "theverge.com",
    "washingtonpost.com",
    "wired.com",
    "wsj.com",
)
ARTICLE_FIELDS = [
    "article_id",
    "seen_at",
    "source_domain",
    "url",
    "language",
    "source_country",
    "title",
    "source_theme_tags",
    "persons",
    "organizations",
    "locations",
    "tone",
    "sharing_image",
    "impact_scope",
    "source_type",
]


class QueryClient(Protocol):
    def query(self, sql: str, *, max_results: int | None = None, maximum_bytes_billed: int | None = None, dry_run: bool = False) -> Any: ...


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
class FetchedGdeltRows:
    sql: str
    rows: list[dict[str, Any]]


class GdeltNewsError(ValueError):
    """Raised for invalid GDELT news tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise GdeltNewsError(f"task_key.bundle must be {BUNDLE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _date_param(params: Mapping[str, Any], key: str, default: date) -> date:
    value = params.get(key)
    if value in (None, ""):
        return default
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise GdeltNewsError(f"params.{key} must be YYYY-MM-DD") from exc


def _topic_categories(params: Mapping[str, Any]) -> list[str]:
    value = params.get("topic_categories")
    if value in (None, ""):
        value = list(DEFAULT_TOPIC_CATEGORIES)
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise GdeltNewsError("params.topic_categories must be a string or list of strings")
    categories = [item.strip().lower() for item in value]
    unknown = sorted(set(categories) - set(TOPIC_CATEGORY_TERMS))
    if unknown:
        raise GdeltNewsError(f"unsupported topic_categories: {unknown}; supported={sorted(TOPIC_CATEGORY_TERMS)}")
    return categories


def _terms(params: Mapping[str, Any]) -> list[str]:
    value = params.get("query_terms") or params.get("terms")
    if value in (None, "", []):
        terms: list[str] = []
        for category in _topic_categories(params):
            terms.extend(TOPIC_CATEGORY_TERMS[category])
        return sorted(set(terms))
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise GdeltNewsError("params.query_terms must be a non-empty string or list of strings")
    return [item.strip() for item in value]


def _string_list_param(params: Mapping[str, Any], key: str, default: tuple[str, ...] = ()) -> list[str]:
    value = params.get(key)
    if value in (None, ""):
        return list(default)
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise GdeltNewsError(f"params.{key} must be a string or list of strings")
    return [item.strip() for item in value]


def _safe_like(value: str) -> str:
    return value.lower().replace("%", "").replace("\\", "").replace("'", "")


def _domain_filter(domains: list[str]) -> str:
    cleaned = [_safe_like(domain).lstrip(".") for domain in domains if domain.strip()]
    if not cleaned:
        return ""
    clauses = [f"LOWER(IFNULL(SourceCommonName,'')) LIKE '%{domain.replace('.com', '')}%' OR LOWER(IFNULL(DocumentIdentifier,'')) LIKE '%{domain}%'" for domain in cleaned]
    return "(" + " OR ".join(clauses) + ")"


def _us_market_focus_filter(params: Mapping[str, Any]) -> str:
    focus = str(params.get("focus") or DEFAULT_FOCUS)
    if focus not in {"us_market", "none"}:
        raise GdeltNewsError("params.focus must be us_market or none")
    if focus == "none":
        return ""
    domains = _string_list_param(params, "source_domain_allowlist", DEFAULT_US_MARKET_DOMAINS)
    domain_clause = _domain_filter(domains)
    us_location_clause = "LOWER(CONCAT(IFNULL(V2Locations,''), ' ', IFNULL(Locations,''))) LIKE '%united states%' OR LOWER(CONCAT(IFNULL(V2Locations,''), ' ', IFNULL(Locations,''))) LIKE '%#us#%'"
    us_market_clause = "LOWER(CONCAT(IFNULL(V2Themes,''), ' ', IFNULL(Themes,''), ' ', IFNULL(AllNames,''), ' ', IFNULL(Organizations,''), ' ', IFNULL(DocumentIdentifier,''))) LIKE '%federal reserve%' OR LOWER(CONCAT(IFNULL(V2Themes,''), ' ', IFNULL(Themes,''), ' ', IFNULL(AllNames,''), ' ', IFNULL(Organizations,''), ' ', IFNULL(DocumentIdentifier,''))) LIKE '%wall street%' OR LOWER(CONCAT(IFNULL(V2Themes,''), ' ', IFNULL(Themes,''), ' ', IFNULL(AllNames,''), ' ', IFNULL(Organizations,''), ' ', IFNULL(DocumentIdentifier,''))) LIKE '%nasdaq%' OR LOWER(CONCAT(IFNULL(V2Themes,''), ' ', IFNULL(Themes,''), ' ', IFNULL(AllNames,''), ' ', IFNULL(Organizations,''), ' ', IFNULL(DocumentIdentifier,''))) LIKE '%s&p 500%' OR LOWER(CONCAT(IFNULL(V2Themes,''), ' ', IFNULL(Themes,''), ' ', IFNULL(AllNames,''), ' ', IFNULL(Organizations,''), ' ', IFNULL(DocumentIdentifier,''))) LIKE '%dow jones%' OR LOWER(CONCAT(IFNULL(V2Themes,''), ' ', IFNULL(Themes,''), ' ', IFNULL(AllNames,''), ' ', IFNULL(Organizations,''), ' ', IFNULL(DocumentIdentifier,''))) LIKE '%u.s. stock%'"
    pieces = [us_location_clause, us_market_clause]
    if domain_clause:
        pieces.append(domain_clause)
    return "(" + " OR ".join(pieces) + ")"


def build_sql(params: Mapping[str, Any]) -> tuple[str, int]:
    today = datetime.now(UTC).date()
    lookback_days = int(params.get("lookback_days", 1))
    start = _date_param(params, "start_date", today - timedelta(days=lookback_days))
    end = _date_param(params, "end_date", today)
    if end < start:
        raise GdeltNewsError("params.end_date must be >= start_date")
    max_rows = int(params.get("max_rows", DEFAULT_MAX_ROWS))
    if max_rows < 1 or max_rows > 1000:
        raise GdeltNewsError("params.max_rows must be between 1 and 1000")
    fields = str(params.get("search_fields") or "source_theme_tags_text")
    if fields not in {"source_theme_tags_text", "url_only", "all_text"}:
        raise GdeltNewsError("params.search_fields must be source_theme_tags_text, url_only, or all_text")
    search_expr = {
        "source_theme_tags_text": "LOWER(CONCAT(IFNULL(V2Themes,''), ' ', IFNULL(Themes,''), ' ', IFNULL(AllNames,''), ' ', IFNULL(Organizations,''), ' ', IFNULL(Persons,'')))",
        "url_only": "LOWER(IFNULL(DocumentIdentifier,''))",
        "all_text": "LOWER(CONCAT(IFNULL(DocumentIdentifier,''), ' ', IFNULL(V2Themes,''), ' ', IFNULL(Themes,''), ' ', IFNULL(AllNames,''), ' ', IFNULL(Organizations,''), ' ', IFNULL(Persons,''), ' ', IFNULL(Locations,'')))",
    }[fields]
    topic_pattern = "|".join(re.escape(_safe_like(term)) for term in _terms(params) if _safe_like(term))
    if not topic_pattern:
        raise GdeltNewsError("topic/category terms resolved to an empty query pattern")
    topic_clause = f"REGEXP_CONTAINS({search_expr}, r'({topic_pattern})')"
    extra_filters: list[str] = []
    focus_filter = _us_market_focus_filter(params)
    if focus_filter:
        extra_filters.append(focus_filter)
    source_domain_contains = params.get("source_domain_contains")
    if source_domain_contains:
        extra_filters.append(f"LOWER(IFNULL(SourceCommonName,'')) LIKE '%{_safe_like(str(source_domain_contains))}%'")
    extra_clause = "" if not extra_filters else "\n  AND " + "\n  AND ".join(extra_filters)
    sql = f"""
SELECT
  GKGRECORDID AS article_id,
  DATE AS gdelt_date,
  SourceCommonName AS source_domain,
  DocumentIdentifier AS url,
  V2Themes AS source_theme_tags,
  V2Persons AS persons,
  V2Organizations AS organizations,
  V2Locations AS locations,
  V2Tone AS tone,
  SharingImage AS sharing_image,
  TranslationInfo AS translation_info
FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE DATE(_PARTITIONTIME) BETWEEN DATE({_sql_string(start.isoformat())}) AND DATE({_sql_string(end.isoformat())})
  AND {topic_clause}{extra_clause}
ORDER BY DATE DESC
LIMIT {max_rows}
""".strip()
    return sql, max_rows


def _default_client() -> QueryClient:
    try:
        from trading_bigquery import BigQueryClient
    except ModuleNotFoundError as exc:
        raise GdeltNewsError("trading_bigquery helper is required; set PYTHONPATH to include /root/projects/trading-main/src") from exc
    return BigQueryClient()


def fetch(context: BundleContext, *, client: QueryClient | None = None) -> tuple[StepResult, FetchedGdeltRows]:
    params = dict(context.task_key.get("params") or {})
    sql, max_rows = build_sql(params)
    client = client or _default_client()
    maximum_bytes_billed = params.get("maximum_bytes_billed")
    maximum_bytes_billed_int = int(maximum_bytes_billed) if maximum_bytes_billed not in (None, "") else None
    dry_run = bool(params.get("dry_run", False))
    result = client.query(sql, max_results=max_rows, maximum_bytes_billed=maximum_bytes_billed_int, dry_run=dry_run)
    rows = list(getattr(result, "rows", []))
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = context.run_dir / "request_manifest.json"
    manifest_path.write_text(json.dumps({"query_terms": sanitize_value(_terms(params)), "topic_categories": sanitize_value(_topic_categories(params)), "focus": str(params.get("focus") or DEFAULT_FOCUS), "source_domain_allowlist": sanitize_value(_string_list_param(params, "source_domain_allowlist", DEFAULT_US_MARKET_DOMAINS)), "max_rows": max_rows, "maximum_bytes_billed": maximum_bytes_billed_int, "dry_run": dry_run, "estimated_total_bytes_processed": getattr(result, "total_bytes_processed", None), "sql": sql, "source": "gdelt_bigquery", "table": "gdelt-bq.gdeltv2.gkg_partitioned", "fetched_at_utc": _now_utc(), "raw_persistence": "not_persisted_by_default"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest_path)], {"bigquery_rows": len(rows)}, details={"table": "gdelt-bq.gdeltv2.gkg_partitioned", "maximum_bytes_billed": maximum_bytes_billed_int, "dry_run": dry_run, "estimated_total_bytes_processed": getattr(result, "total_bytes_processed", None)}), FetchedGdeltRows(sql, rows)


def _seen_at(row: Mapping[str, Any]) -> str:
    value = row.get("gdelt_date") or ""
    text = str(value)
    if re.fullmatch(r"\d{14}", text):
        dt = datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        return dt.astimezone(ET).isoformat()
    if re.fullmatch(r"\d{8}", text):
        dt = datetime.strptime(text, "%Y%m%d").replace(tzinfo=UTC)
        return dt.astimezone(ET).isoformat()
    return ""


def _tone(row: Mapping[str, Any]) -> str:
    tone = row.get("tone")
    if tone is None:
        return ""
    return str(tone).split(",", 1)[0]


def normalize_rows(rows: list[dict[str, Any]], *, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    impact_scope = str(params.get("impact_scope") or "market;sector;industry;theme")
    output: list[dict[str, Any]] = []
    for row in rows:
        url = str(row.get("url") or "").strip()
        article_id = str(row.get("article_id") or url).strip()
        if not url or not article_id:
            continue
        output.append({
            "article_id": article_id,
            "seen_at": _seen_at(row),
            "source_domain": str(row.get("source_domain") or ""),
            "url": url,
            "language": "",
            "source_country": "",
            "title": "",
            "source_theme_tags": str(row.get("source_theme_tags") or ""),
            "persons": str(row.get("persons") or ""),
            "organizations": str(row.get("organizations") or ""),
            "locations": str(row.get("locations") or ""),
            "tone": _tone(row),
            "sharing_image": str(row.get("sharing_image") or ""),
            "impact_scope": impact_scope,
            "source_type": "gdelt_gkg_article",
        })
    return output


def clean(context: BundleContext, fetched: FetchedGdeltRows) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    rows = normalize_rows(fetched.rows, params=params)
    if not rows:
        raise GdeltNewsError("GDELT query produced zero usable article rows")
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    path = context.cleaned_dir / "gdelt_article.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_value(row), sort_keys=True) + "\n")
    schema_path = context.cleaned_dir / "schema.json"
    schema_path.write_text(json.dumps({"gdelt_article": ARTICLE_FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path), str(schema_path)], {"gdelt_article": len(rows)}, details={"columns": ARTICLE_FIELDS})


def save(context: BundleContext, clean_result: StepResult) -> StepResult:
    rows = [json.loads(line) for line in (context.cleaned_dir / "gdelt_article.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / "gdelt_article.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ARTICLE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return StepResult("succeeded", [str(path)], dict(clean_result.row_counts), details={"format": "csv", "columns": ARTICLE_FIELDS})


def write_receipt(context: BundleContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: BaseException | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "bundle": BUNDLE, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    run_id = str(context.metadata["run_id"])
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": run_id, "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != run_id] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "bundle": BUNDLE})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": run_id, "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str, client: QueryClient | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, fetched = fetch(context, client=client)
        clean_result = clean(context, fetched)
        save_result = save(context, clean_result)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
