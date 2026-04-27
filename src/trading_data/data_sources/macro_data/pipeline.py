"""Actual API-backed macro_data acquisition bundle.

This bundle intentionally starts narrow but real: each supported source builds
an actual provider request, parses the provider response shape, normalizes rows,
and writes cleaned development output under ``storage``. It does not persist
full raw provider responses by default.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_data.source_availability.http import HttpClient, HttpResult
from trading_data.source_availability.sanitize import sanitize_url, sanitize_value
from trading_data.source_availability.secrets import load_secret_alias, public_secret_summary
from trading_data.data_sources.macro_data.interfaces import MACRO_INTERFACES, params_for_data_kind


SUPPORTED_SOURCES = {"bls", "census", "bea", "us_treasury_fiscal_data", "fred"}
DEFAULT_TIMEOUT_SECONDS = 20
MACRO_RELEASE_FIELDS = ["metric", "release_time", "effective_until", "value"]  # transient cleaned evidence only; final saved output is macro_release_event.csv
MACRO_RELEASE_EVENT_FIELDS = [
    "event_id",
    "canonical_event_id",
    "dedup_status",
    "source_priority",
    "impact_scope",
    "impacted_universe",
    "primary_impact_target",
    "security_id",
    "symbol",
    "event_time_et",
    "effective_time_et",
    "event_type",
    "source_type",
    "source_ref",
    "source_url",
    "title",
    "summary",
    "metric",
    "value",
    "analysis_report_url",
    "analysis_status",
    "coverage_reason",
    "taxonomy_context",
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
class FetchedPayload:
    source: str
    endpoint: str
    http_status: int | None
    payload: Any
    request: dict[str, Any]
    secret_alias: dict[str, Any] | None = None


class MacroDataError(ValueError):
    """Raised for unsupported or invalid macro_data task params."""


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(mapping: dict[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise MacroDataError(f"macro_data.params.{key} is required")
    return value


def _ensure_list(value: Any, *, key: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) and item for item in value):
        return value
    raise MacroDataError(f"macro_data.params.{key} must be a non-empty string or list of strings")


def _json_response(result: HttpResult) -> Any:
    if result.status is None:
        raise MacroDataError(f"request failed before HTTP response: {result.error_type}: {result.error_message}")
    if result.status < 200 or result.status >= 300:
        raise MacroDataError(f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}")
    return result.json()


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != "macro_data":
        raise MacroDataError("task_key.bundle must be macro_data")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', 'macro_data_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(
        task_key=task_key,
        run_dir=run_dir,
        cleaned_dir=run_dir / "cleaned",
        saved_dir=run_dir / "saved",
        receipt_path=output_root / "completion_receipt.json",
        metadata={"run_id": run_id, "started_at": _now_utc()},
    )


def _resolve_params(params: dict[str, Any]) -> dict[str, Any]:
    data_kind = params.get("data_kind")
    if data_kind:
        if data_kind not in MACRO_INTERFACES:
            raise MacroDataError(f"unsupported macro_data data_kind {data_kind!r}; supported={sorted(MACRO_INTERFACES)}")
        resolved = params_for_data_kind(str(data_kind))
        resolved.update(params)
        return resolved
    return params


def fetch(context: BundleContext, *, client: HttpClient | None = None) -> tuple[StepResult, FetchedPayload]:
    params = _resolve_params(dict(context.task_key.get("params") or {}))
    source = str(_required(params, "source"))
    if source not in SUPPORTED_SOURCES:
        raise MacroDataError(f"unsupported macro_data source {source!r}; supported={sorted(SUPPORTED_SOURCES)}")
    client = client or HttpClient(timeout_seconds=int(params.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)))
    fetched = _fetch_by_source(source, params, client)
    manifest_path = context.run_dir / "request_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": fetched.source,
        "endpoint": sanitize_url(fetched.endpoint),
        "http_status": fetched.http_status,
        "request": sanitize_value(fetched.request),
        "secret_alias": fetched.secret_alias,
        "fetched_at_utc": _now_utc(),
        "raw_persistence": "not_persisted_by_default",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return (
        StepResult(
            status="succeeded",
            references=[str(manifest_path)],
            row_counts={"raw_payloads": 1},
            details={"source": source, "http_status": fetched.http_status},
        ),
        fetched,
    )


def _fetch_by_source(source: str, params: dict[str, Any], client: HttpClient) -> FetchedPayload:
    if source == "bls":
        secret = load_secret_alias("bls")
        payload: dict[str, Any] = {
            "seriesid": _ensure_list(_required(params, "series_ids"), key="series_ids"),
        }
        for key in ("startyear", "endyear"):
            if key in params:
                payload[key] = str(params[key])
        if secret.values.get("api_key"):
            payload["registrationkey"] = str(secret.values["api_key"])
        result = client.post_json("https://api.bls.gov/publicAPI/v2/timeseries/data/", payload=payload)
        return FetchedPayload(source, result.url, result.status, _json_response(result), {"method": "POST", "json": payload}, public_secret_summary(secret))

    if source == "census":
        secret = load_secret_alias("census")
        dataset = str(_required(params, "dataset"))
        api_params: dict[str, str] = {"get": str(_required(params, "get"))}
        for key in ("for", "in", "time", "ucgid"):
            if key in params:
                api_params[key] = str(params[key])
        if isinstance(params.get("predicates"), dict):
            api_params.update({str(k): str(v) for k, v in params["predicates"].items()})
        if secret.values.get("api_key"):
            api_params["key"] = str(secret.values["api_key"])
        url = "https://api.census.gov/data/" + dataset.strip("/")
        result = client.get(url, params=api_params)
        return FetchedPayload(source, result.url, result.status, _json_response(result), {"method": "GET", "params": api_params}, public_secret_summary(secret))

    if source == "bea":
        secret = load_secret_alias("bea")
        api_key = secret.values.get("api_key")
        if not api_key:
            raise MacroDataError("BEA requires /root/secrets/bea.json api_key or BEA_SECRET_ALIAS override")
        api_params = {str(k): str(v) for k, v in dict(_required(params, "api_params")).items()}
        api_params.setdefault("UserID", str(api_key))
        api_params.setdefault("ResultFormat", "JSON")
        result = client.get("https://apps.bea.gov/api/data/", params=api_params)
        return FetchedPayload(source, result.url, result.status, _json_response(result), {"method": "GET", "params": api_params}, public_secret_summary(secret))

    if source == "us_treasury_fiscal_data":
        endpoint = str(_required(params, "endpoint"))
        if not endpoint.startswith("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"):
            endpoint = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/" + endpoint.strip("/")
        api_params = {str(k): str(v) for k, v in dict(params.get("api_params") or {}).items()}
        api_params.setdefault("page[size]", str(params.get("page_size", 100)))
        result = client.get(endpoint, params=api_params)
        return FetchedPayload(source, result.url, result.status, _json_response(result), {"method": "GET", "params": api_params}, None)

    if source == "fred":
        secret = load_secret_alias("fred")
        api_key = secret.values.get("api_key")
        if not api_key:
            raise MacroDataError("FRED requires /root/secrets/fred.json api_key or FRED_SECRET_ALIAS override")
        endpoint_name = str(params.get("endpoint", "series/observations"))
        if endpoint_name not in {"series/observations", "series/search", "series/vintagedates"}:
            raise MacroDataError("FRED endpoint must be one of series/observations, series/search, series/vintagedates")
        api_params = {str(k): str(v) for k, v in dict(params.get("api_params") or {}).items()}
        if "series_id" in params:
            api_params.setdefault("series_id", str(params["series_id"]))
        api_params.setdefault("api_key", str(api_key))
        api_params.setdefault("file_type", "json")
        result = client.get(f"https://api.stlouisfed.org/fred/{endpoint_name}", params=api_params)
        return FetchedPayload(source, result.url, result.status, _json_response(result), {"method": "GET", "params": api_params}, public_secret_summary(secret))

    raise AssertionError(source)


def _stable_macro_event_id(row: dict[str, Any], source: str) -> str:
    seed = f"{source}|{row.get('metric')}|{row.get('release_time')}|{row.get('value')}"
    return "macro_evt_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10].upper()


def _macro_release_event_rows(params: dict[str, Any], rows: list[dict[str, Any]], fetched: FetchedPayload) -> list[dict[str, Any]]:
    impact_scope = str(params.get("impact_scope") or "market")
    impacted_universe = str(params.get("impacted_universe") or "US_MARKET;rates;USD;equities")
    primary_impact_target = str(params.get("primary_impact_target") or "US_MARKET")
    source_url = str(params.get("source_url") or sanitize_url(fetched.endpoint) or "")
    source_ref_prefix = str(params.get("source_ref") or fetched.source)
    events: list[dict[str, Any]] = []
    for row in rows:
        event_id = _stable_macro_event_id(row, fetched.source)
        metric = str(row.get("metric") or "macro_release")
        value = row.get("value", "")
        taxonomy_context = {
            "provider": fetched.source,
            "metric": metric,
            "actual_value": value,
            "consensus_value": params.get("consensus_value"),
            "previous_value": params.get("previous_value"),
            "revision_value": params.get("revision_value"),
            "surprise_status": "pending_consensus_source" if params.get("consensus_value") in (None, "") else "available",
        }
        events.append({
            "event_id": event_id,
            "canonical_event_id": event_id,
            "dedup_status": "canonical",
            "source_priority": 100,
            "impact_scope": impact_scope,
            "impacted_universe": impacted_universe,
            "primary_impact_target": primary_impact_target,
            "security_id": "",
            "symbol": "",
            "event_time_et": row["release_time"],
            "effective_time_et": str(params.get("effective_time") or row["release_time"]),
            "event_type": "macro_release_event",
            "source_type": "official_macro_release",
            "source_ref": f"{source_ref_prefix}:{metric}",
            "source_url": source_url,
            "title": str(params.get("event_title") or f"{metric} macro release"),
            "summary": str(params.get("event_summary") or f"Official macro release for {metric}; actual value={value}."),
            "metric": metric,
            "value": value,
            "analysis_report_url": str(params.get("analysis_report_url") or ""),
            "analysis_status": str(params.get("analysis_status") or "not_requested"),
            "coverage_reason": "official macro release is source of truth",
            "taxonomy_context": json.dumps(taxonomy_context, sort_keys=True),
        })
    return events


def clean(context: BundleContext, fetched: FetchedPayload) -> StepResult:
    params = _resolve_params(dict(context.task_key.get("params") or {}))
    raw_rows = _normalize_rows(fetched.source, fetched.payload)
    if not raw_rows:
        raise MacroDataError(f"{fetched.source} response produced zero normalized rows")
    rows = _normalize_release_rows(params, raw_rows)
    event_rows = _macro_release_event_rows(params, rows, fetched)
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    output = context.cleaned_dir / "macro_release.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_value(row), sort_keys=True) + "\n")
    event_output = context.cleaned_dir / "macro_release_event.jsonl"
    with event_output.open("w", encoding="utf-8") as handle:
        for row in event_rows:
            handle.write(json.dumps(sanitize_value(row), sort_keys=True) + "\n")
    schema_path = context.cleaned_dir / "schema.json"
    schema_path.write_text(json.dumps({"macro_release": MACRO_RELEASE_FIELDS, "macro_release_event": MACRO_RELEASE_EVENT_FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(
        status="succeeded",
        references=[str(output), str(event_output), str(schema_path)],
        row_counts={"macro_release_evidence": len(rows), "macro_release_event": len(event_rows)},
        details={"macro_release_columns": MACRO_RELEASE_FIELDS, "macro_release_event_columns": MACRO_RELEASE_EVENT_FIELDS, "source": fetched.source},
    )


def _normalize_rows(source: str, payload: Any) -> list[dict[str, Any]]:
    if source == "bls":
        series = payload.get("Results", {}).get("series", []) if isinstance(payload, dict) else []
        rows: list[dict[str, Any]] = []
        for item in series:
            series_id = item.get("seriesID")
            for obs in item.get("data", []):
                rows.append({"source": source, "series_id": series_id, **obs})
        return rows
    if source == "census":
        if isinstance(payload, list) and payload and isinstance(payload[0], list):
            header = [str(name) for name in payload[0]]
            return [{"source": source, **dict(zip(header, row, strict=False))} for row in payload[1:]]
        return []
    if source == "bea":
        results = payload.get("BEAAPI", {}).get("Results", {}) if isinstance(payload, dict) else {}
        data = results.get("Data") or results.get("Parameter") or results.get("ParamValue") or []
        if isinstance(data, dict):
            data = [data]
        return [{"source": source, **row} for row in data if isinstance(row, dict)]
    if source == "us_treasury_fiscal_data":
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return [{"source": source, **row} for row in data if isinstance(row, dict)]
    if source == "fred":
        for key in ("observations", "seriess", "vintage_dates"):
            data = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(data, list):
                if data and isinstance(data[0], dict):
                    return [{"source": source, **row} for row in data]
                return [{"source": source, "value": value} for value in data]
        return []
    return []



def _normalize_release_rows(params: dict[str, Any], raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    release_time = str(_required(params, "release_time"))
    effective_until = params.get("effective_until", "")
    metric_override = params.get("metric")
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        metric = str(metric_override or raw.get("series_id") or raw.get("seriesID") or raw.get("metric") or raw.get("field") or params.get("series_id") or params.get("source"))
        value = raw.get("value")
        if value is None:
            value = raw.get("cell_value")
        if value is None:
            value = raw.get("DataValue")
        if value is None:
            continue
        rows.append({"metric": metric, "release_time": release_time, "effective_until": effective_until, "value": value})
    if not rows:
        raise MacroDataError("macro_data response produced no rows with a usable value field")
    return rows

def save(context: BundleContext, clean_result: StepResult) -> StepResult:
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    event_csv_path = context.saved_dir / "macro_release_event.csv"
    event_rows = [json.loads(line) for line in (context.cleaned_dir / "macro_release_event.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    with event_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MACRO_RELEASE_EVENT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(event_rows)
    return StepResult(
        status="succeeded",
        references=[str(event_csv_path)],
        row_counts={"macro_release_event": clean_result.row_counts["macro_release_event"]},
        details={"format": "csv", "macro_release_event_columns": MACRO_RELEASE_EVENT_FIELDS, "transient_evidence": "cleaned/macro_release.jsonl"},
    )


def write_receipt(
    context: BundleContext,
    *,
    status: str,
    fetch_result: StepResult | None = None,
    clean_result: StepResult | None = None,
    save_result: StepResult | None = None,
    error: BaseException | None = None,
) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "bundle": "macro_data", "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    run_id = str(context.metadata["run_id"])
    entry = {
        "run_id": run_id,
        "status": status,
        "started_at": context.metadata.get("started_at"),
        "completed_at": _now_utc(),
        "output_dir": str(context.run_dir),
        "outputs": (save_result.references if save_result else []),
        "row_counts": (save_result.row_counts if save_result else clean_result.row_counts if clean_result else {}),
        "steps": {
            "fetch": asdict(fetch_result) if fetch_result else None,
            "clean": asdict(clean_result) if clean_result else None,
            "save": asdict(save_result) if save_result else None,
        },
        "error": None if error is None else {"type": type(error).__name__, "message": str(error)},
    }
    runs = [run for run in existing.get("runs", []) if run.get("run_id") != run_id]
    runs.append(entry)
    existing.update({"task_id": context.task_key.get("task_id"), "bundle": "macro_data", "runs": runs})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(
        status=status,
        references=[str(context.receipt_path), *entry["outputs"]],
        row_counts=entry["row_counts"],
        details={"run_id": run_id, "error": entry["error"]},
    )


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    fetch_result: StepResult | None = None
    clean_result: StepResult | None = None
    save_result: StepResult | None = None
    try:
        fetch_result, fetched = fetch(context, client=client)
        clean_result = clean(context, fetched)
        save_result = save(context, clean_result)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
