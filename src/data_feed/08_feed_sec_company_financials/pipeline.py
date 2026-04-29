"""SEC EDGAR company financials acquisition feed.

Fetches official SEC EDGAR JSON APIs and persists compact normalized CSV rows.
Raw SEC responses are not persisted by default because companyfacts can be large.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from feed_availability.__main__ import DEFAULT_SEC_USER_AGENT
from feed_availability.http import HttpClient, HttpResult
from feed_availability.sanitize import sanitize_url, sanitize_value

FEED = "08_feed_sec_company_financials"
DEFAULT_TIMEOUT_SECONDS = 20
SUPPORTED_DATA_KINDS = {"sec_submission", "sec_company_fact", "sec_company_concept", "sec_xbrl_frame"}
FIELD_ORDER = {
    "sec_submission": ["cik", "company_name", "accession_number", "filing_date", "report_date", "form", "primary_document", "primary_doc_description"],
    "sec_company_fact": ["cik", "entity_name", "taxonomy", "tag", "label", "description", "unit", "fy", "fp", "form", "filed", "frame", "end", "value", "accession_number"],
    "sec_company_concept": ["cik", "entity_name", "taxonomy", "tag", "label", "description", "unit", "fy", "fp", "form", "filed", "frame", "end", "value", "accession_number"],
    "sec_xbrl_frame": ["taxonomy", "tag", "unit", "frame", "cik", "entity_name", "loc", "end", "value", "accession_number"],
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
class FetchedSecPayload:
    data_kind: str
    cik: str | None
    endpoint: str
    payload: Any
    http_status: int | None
    request: dict[str, Any]


class SecCompanyFinancialsError(ValueError):
    """Raised for invalid SEC company financial tasks."""


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise SecCompanyFinancialsError(f"{FEED}.params.{key} is required")
    return value


def _normalize_cik(value: Any) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise SecCompanyFinancialsError("cik must contain digits only")
    return text.zfill(10)


def build_context(task_key: dict[str, Any], run_id: str) -> FeedContext:
    if task_key.get("feed") != FEED:
        raise SecCompanyFinancialsError(f"task_key.feed must be {FEED}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', FEED + '_task')}"))
    run_dir = output_root / "runs" / run_id
    return FeedContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _json_response(result: HttpResult) -> Any:
    if result.status is None:
        raise SecCompanyFinancialsError(f"request failed before HTTP response: {result.error_type}: {result.error_message}")
    if result.status < 200 or result.status >= 300:
        raise SecCompanyFinancialsError(f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}")
    return result.json()


def fetch(context: FeedContext, *, client: HttpClient | None = None, sec_user_agent: str = DEFAULT_SEC_USER_AGENT) -> tuple[StepResult, FetchedSecPayload]:
    params = dict(context.task_key.get("params") or {})
    data_kind = str(params.get("data_kind") or "sec_company_fact")
    if data_kind not in SUPPORTED_DATA_KINDS:
        raise SecCompanyFinancialsError(f"unsupported SEC data_kind {data_kind!r}; supported={sorted(SUPPORTED_DATA_KINDS)}")
    client = client or HttpClient(timeout_seconds=int(params.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)))
    headers = {"User-Agent": str(sec_user_agent), "Accept-Encoding": "identity", "Accept": "application/json"}
    cik = _normalize_cik(_required(params, "cik")) if data_kind != "sec_xbrl_frame" else (str(params.get("cik")).zfill(10) if params.get("cik") else None)

    if data_kind == "sec_submission":
        endpoint = f"https://data.sec.gov/submissions/CIK{cik}.json"
        request = {"data_kind": data_kind, "cik": cik}
    elif data_kind == "sec_company_fact":
        endpoint = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        request = {"data_kind": data_kind, "cik": cik}
    elif data_kind == "sec_company_concept":
        taxonomy = str(params.get("taxonomy") or "us-gaap")
        tag = str(_required(params, "tag"))
        endpoint = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json"
        request = {"data_kind": data_kind, "cik": cik, "taxonomy": taxonomy, "tag": tag}
    else:
        taxonomy = str(params.get("taxonomy") or "us-gaap")
        tag = str(_required(params, "tag"))
        unit = str(params.get("unit") or "USD")
        frame = str(_required(params, "frame"))
        endpoint = f"https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{frame}.json"
        request = {"data_kind": data_kind, "taxonomy": taxonomy, "tag": tag, "unit": unit, "frame": frame}

    result = client.get(endpoint, headers=headers)
    payload = _json_response(result)
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = context.run_dir / "request_manifest.json"
    manifest_path.write_text(json.dumps({"endpoint": sanitize_url(result.url), "http_status": result.status, "request": sanitize_value(request), "fetched_at_utc": _now_utc(), "raw_persistence": "not_persisted_by_default", "user_agent_present": bool(sec_user_agent)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest_path)], {"raw_sec_payloads": 1}, details=request), FetchedSecPayload(data_kind, cik, result.url, payload, result.status, request)


def _fact_value_rows(cik: str, entity_name: str, taxonomy: str, tag: str, fact: Mapping[str, Any], *, unit_filter: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    units = fact.get("units")
    if not isinstance(units, Mapping):
        return rows
    for unit, values in units.items():
        if unit_filter and unit != unit_filter:
            continue
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, Mapping):
                continue
            rows.append({
                "cik": cik,
                "entity_name": entity_name,
                "taxonomy": taxonomy,
                "tag": tag,
                "label": fact.get("label"),
                "description": fact.get("description"),
                "unit": unit,
                "fy": value.get("fy"),
                "fp": value.get("fp"),
                "form": value.get("form"),
                "filed": value.get("filed"),
                "frame": value.get("frame"),
                "end": value.get("end"),
                "value": value.get("val"),
                "accession_number": value.get("accn"),
            })
    return rows


def normalize_rows(fetched: FetchedSecPayload, *, params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    params = params or {}
    payload = fetched.payload
    if not isinstance(payload, Mapping):
        raise SecCompanyFinancialsError("SEC response was not a JSON object")
    data_kind = fetched.data_kind
    if data_kind == "sec_submission":
        recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload.get("filings"), Mapping) else {}
        accession_numbers = recent.get("accessionNumber", []) if isinstance(recent, Mapping) else []
        rows = []
        for idx, accession in enumerate(accession_numbers if isinstance(accession_numbers, list) else []):
            def pick(key: str) -> Any:
                values = recent.get(key, [])
                return values[idx] if isinstance(values, list) and idx < len(values) else None
            rows.append({"cik": fetched.cik, "company_name": payload.get("name"), "accession_number": accession, "filing_date": pick("filingDate"), "report_date": pick("reportDate"), "form": pick("form"), "primary_document": pick("primaryDocument"), "primary_doc_description": pick("primaryDocDescription")})
        return rows
    if data_kind == "sec_company_fact":
        rows: list[dict[str, Any]] = []
        facts = payload.get("facts", {})
        if not isinstance(facts, Mapping):
            return rows
        taxonomy_filter = params.get("taxonomy")
        tag_filter = params.get("tag")
        unit_filter = params.get("unit")
        for taxonomy, tags in facts.items():
            if taxonomy_filter and taxonomy != taxonomy_filter:
                continue
            if not isinstance(tags, Mapping):
                continue
            for tag, fact in tags.items():
                if tag_filter and tag != tag_filter:
                    continue
                if isinstance(fact, Mapping):
                    rows.extend(_fact_value_rows(str(payload.get("cik") or fetched.cik or ""), str(payload.get("entityName") or ""), str(taxonomy), str(tag), fact, unit_filter=str(unit_filter) if unit_filter else None))
        return rows
    if data_kind == "sec_company_concept":
        taxonomy = str(fetched.request.get("taxonomy") or params.get("taxonomy") or "")
        tag = str(fetched.request.get("tag") or params.get("tag") or "")
        return _fact_value_rows(str(payload.get("cik") or fetched.cik or ""), str(payload.get("entityName") or ""), taxonomy, tag, payload, unit_filter=str(params.get("unit")) if params.get("unit") else None)
    if data_kind == "sec_xbrl_frame":
        rows = []
        for item in payload.get("data", []) if isinstance(payload.get("data"), list) else []:
            if isinstance(item, Mapping):
                rows.append({"taxonomy": fetched.request.get("taxonomy"), "tag": fetched.request.get("tag"), "unit": fetched.request.get("unit"), "frame": fetched.request.get("frame"), "cik": item.get("cik"), "entity_name": item.get("entityName"), "loc": item.get("loc"), "end": item.get("end"), "value": item.get("val"), "accession_number": item.get("accn")})
        return rows
    raise AssertionError(data_kind)


def clean(context: FeedContext, fetched: FetchedSecPayload) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    rows = normalize_rows(fetched, params=params)
    if not rows:
        raise SecCompanyFinancialsError(f"{fetched.data_kind} response produced zero normalized rows")
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = context.cleaned_dir / f"{fetched.data_kind}.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_value(row), sort_keys=True) + "\n")
    schema_path = context.cleaned_dir / "schema.json"
    schema_path.write_text(json.dumps({fetched.data_kind: FIELD_ORDER[fetched.data_kind], "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(jsonl_path), str(schema_path)], {fetched.data_kind: len(rows)}, details={"columns": FIELD_ORDER[fetched.data_kind], "format": "jsonl"})


def save(context: FeedContext, clean_result: StepResult) -> StepResult:
    data_kind = next(iter(clean_result.row_counts))
    rows = [json.loads(line) for line in (context.cleaned_dir / f"{data_kind}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / f"{data_kind}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELD_ORDER[data_kind], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return StepResult("succeeded", [str(path)], dict(clean_result.row_counts), details={"format": "csv", "columns": FIELD_ORDER[data_kind]})


def write_receipt(context: FeedContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: BaseException | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "feed": FEED, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": context.metadata["run_id"], "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != context.metadata["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "feed": FEED})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": context.metadata["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None, sec_user_agent: str = DEFAULT_SEC_USER_AGENT) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, fetched = fetch(context, client=client, sec_user_agent=sec_user_agent)
        clean_result = clean(context, fetched)
        save_result = save(context, clean_result)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
