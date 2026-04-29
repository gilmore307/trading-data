"""ETF issuer holdings interface bundle.

The bundle normalizes issuer-published holdings into a single snapshot row shape.
It intentionally starts as a conservative interface scaffold: users provide an
official source URL and captured/source text, while issuer-specific live fetch
adapters can be added after the ETF-symbol-to-issuer mapping table is accepted.
"""

from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Mapping

from source_availability.sanitize import sanitize_value

BUNDLE = "06_source_etf_holdings"
FIELDS = [
    "etf_symbol",
    "issuer_name",
    "as_of_date",
    "holding_symbol",
    "holding_name",
    "weight",
    "shares",
    "market_value",
    "cusip",
    "sedol",
    "asset_class",
    "sector_type",
    "source_url",
]

ISSUER_FETCH_PATTERNS = {
    "ishares": "official CSV ajax endpoint from iShares fund page",
    "blackrock": "official CSV ajax endpoint from iShares fund page",
    "state_street": "official SSGA XLSX holdings-daily-us-en-<ticker>.xlsx",
    "spdr": "official SSGA XLSX holdings-daily-us-en-<ticker>.xlsx",
    "sector_spdr": "official SSGA XLSX holdings-daily-us-en-<ticker>.xlsx",
    "global_x": "official assets.globalxetfs.com dated full-holdings CSV",
    "ark": "official assets.ark-funds.com fund-documents CSV",
    "first_trust": "official ftportfolios.com holdings HTML table",
    "invesco": "official dng-api.invesco.com holdings JSON endpoint",
    "us_global": "official usglobaletfs.com fund-page holdings table",
    "vanguard": "official JS-rendered Vanguard profile holdings table",
    "vaneck": "official vaneck.com holdings XLSX download; may need browser/session headers",
}


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
class SourcePayload:
    kind: str
    text: str
    source_url: str


class EtfHoldingsError(ValueError):
    """Raised for invalid ETF holdings tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise EtfHoldingsError(f"task_key.bundle must be {BUNDLE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _required(params: Mapping[str, Any], key: str) -> str:
    value = str(params.get(key) or "").strip()
    if not value:
        raise EtfHoldingsError(f"params.{key} is required")
    return value


def _etf_symbol_param(params: Mapping[str, Any]) -> str:
    value = str(params.get("etf_symbol") or params.get("etf_ticker") or "").strip().upper()
    if not value:
        raise EtfHoldingsError("params.etf_symbol is required")
    return value


def fetch(context: BundleContext) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    etf_symbol = _etf_symbol_param(params)
    issuer = str(params.get("issuer") or _required(params, "issuer_name")).lower().replace(" ", "_")
    source_url = str(params.get("source_url") or "")
    payload: SourcePayload | None = None
    for kind in ("csv", "html", "json"):
        if params.get(kind + "_path"):
            payload = SourcePayload(kind, Path(str(params[kind + "_path"])).read_text(encoding="utf-8"), source_url)
            break
        if params.get(kind + "_text"):
            payload = SourcePayload(kind, str(params[kind + "_text"]), source_url)
            break
        if params.get(kind):
            payload = SourcePayload(kind, str(params[kind]), source_url)
            break
    if payload is None:
        raise EtfHoldingsError("provide one of params.csv_path/csv_text/html_path/html/json_path/json_text; live issuer fetch adapters are not enabled yet")
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "bundle": BUNDLE,
        "etf_symbol": etf_symbol,
        "issuer_name": issuer,
        "issuer_pattern": ISSUER_FETCH_PATTERNS.get(issuer, "issuer adapter pending mapping review"),
        "source_url": source_url,
        "source_payload_kind": payload.kind,
        "fetched_at_utc": _now_utc(),
        "raw_persistence": "not_persisted_by_default",
    }
    path = context.run_dir / "request_manifest.json"
    path.write_text(json.dumps(sanitize_value(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path)], {"source_payloads": 1}, details=manifest), payload


def _canonical_key(key: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    aliases = {
        "ticker": "holding_symbol",
        "symbol": "holding_symbol",
        "holding_symbol": "holding_symbol",
        "name": "holding_name",
        "holding": "holding_name",
        "holdings": "holding_name",
        "company": "holding_name",
        "security_name": "holding_name",
        "weight": "weight",
        "weight_%": "weight",
        "weight_percent": "weight",
        "%_of_net_assets": "weight",
        "%_of_fund": "weight",
        "shares": "shares",
        "shares_held": "shares",
        "market_value": "market_value",
        "market_value_$": "market_value",
        "cusip": "cusip",
        "sedol": "sedol",
        "asset_class": "asset_class",
        "sector": "sector_type",
        "sector_type": "sector_type",
        "date": "as_of_date",
        "as_of_date": "as_of_date",
    }
    return aliases.get(key, key)


def _clean_num(value: Any) -> str:
    text = str(value or "").strip().replace("$", "").replace(",", "").replace("%", "")
    return text


def _normalize_row(raw: Mapping[str, Any], *, etf_symbol: str, issuer: str, source_url: str, default_as_of: str) -> dict[str, str]:
    mapped = {_canonical_key(str(key)): str(value or "").strip() for key, value in raw.items()}
    return {
        "etf_symbol": etf_symbol,
        "issuer_name": issuer,
        "as_of_date": mapped.get("as_of_date") or default_as_of,
        "holding_symbol": mapped.get("holding_symbol", ""),
        "holding_name": mapped.get("holding_name", ""),
        "weight": _clean_num(mapped.get("weight")),
        "shares": _clean_num(mapped.get("shares")),
        "market_value": _clean_num(mapped.get("market_value")),
        "cusip": mapped.get("cusip", ""),
        "sedol": mapped.get("sedol", ""),
        "asset_class": mapped.get("asset_class", ""),
        "sector_type": mapped.get("sector_type", ""),
        "source_url": source_url,
    }


def _parse_csv(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if "ticker" in line.lower() and ("weight" in line.lower() or "market value" in line.lower() or "% of" in line.lower())), 0)
    return list(csv.DictReader(StringIO("\n".join(lines[start:]))))


def _clean_cell(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_html(text: str) -> list[dict[str, Any]]:
    rows = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, flags=re.I | re.S):
        rows.append([_clean_cell(cell) for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html, flags=re.I | re.S)])
    header_i = next((i for i, row in enumerate(rows) if any(cell.lower() in {"ticker", "symbol"} for cell in row) and any("weight" in cell.lower() or "%" in cell for cell in row)), -1)
    if header_i < 0:
        return []
    headers = rows[header_i]
    parsed = []
    for row in rows[header_i + 1:]:
        if len(row) < 2:
            continue
        parsed.append({header: row[idx] if idx < len(row) else "" for idx, header in enumerate(headers)})
    return parsed


def _iter_json_rows(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                yield item
    elif isinstance(value, Mapping):
        for key in ("holdings", "data", "rows", "fundHoldings"):
            if key in value:
                yield from _iter_json_rows(value[key])


def clean(context: BundleContext, payload: SourcePayload) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    etf_symbol = _etf_symbol_param(params)
    issuer = str(params.get("issuer") or _required(params, "issuer_name")).lower().replace(" ", "_")
    as_of_date = str(params.get("as_of_date") or "")
    if payload.kind == "csv":
        raw_rows = _parse_csv(payload.text)
    elif payload.kind == "html":
        raw_rows = _parse_html(payload.text)
    elif payload.kind == "json":
        raw_rows = list(_iter_json_rows(json.loads(payload.text)))
    else:
        raise EtfHoldingsError(f"unsupported source payload kind {payload.kind}")
    rows = [_normalize_row(row, etf_symbol=etf_symbol, issuer=issuer, source_url=payload.source_url, default_as_of=as_of_date) for row in raw_rows]
    rows = [row for row in rows if row["holding_symbol"] or row["holding_name"]]
    if not rows:
        raise EtfHoldingsError("ETF holdings source produced zero parseable holding rows")
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    path = context.cleaned_dir / "etf_holding_snapshot.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_value(row), sort_keys=True) + "\n")
    schema = context.cleaned_dir / "schema.json"
    schema.write_text(json.dumps({"etf_holding_snapshot": FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path), str(schema)], {"etf_holding_snapshot": len(rows)}, details={"columns": FIELDS})


def save(context: BundleContext, clean_result: StepResult) -> StepResult:
    rows = [json.loads(line) for line in (context.cleaned_dir / "etf_holding_snapshot.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / "etf_holding_snapshot.csv"
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
        fetch_result, payload = fetch(context)
        clean_result = clean(context, payload)
        save_result = save(context, clean_result)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
