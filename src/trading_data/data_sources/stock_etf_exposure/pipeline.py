"""Derived stock-to-ETF exposure bundle.

This bundle turns official ETF holdings snapshots into point-in-time stock
exposure rows for SecuritySelectionModel. It does not fetch raw provider data;
ETF issuer acquisition remains owned by ``etf_holdings``.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from trading_data.source_availability.sanitize import sanitize_value

BUNDLE = "stock_etf_exposure"
FIELDS = [
    "as_of_date",
    "symbol",
    "exposed_etfs",
    "top_exposure_etf",
    "total_etf_exposure_score",
    "weighted_sector_score",
    "weighted_theme_score",
    "style_tags",
    "source_etf_count",
    "source_snapshot_refs",
    "available_time_et",
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
class SourcePayload:
    holdings: list[dict[str, str]]
    etf_scores: dict[str, dict[str, Any]]


class StockEtfExposureError(ValueError):
    """Raised for invalid stock_etf_exposure tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise StockEtfExposureError(f"task_key.bundle must be {BUNDLE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _require(params: Mapping[str, Any], key: str) -> Any:
    value = params.get(key)
    if value in (None, "", []):
        raise StockEtfExposureError(f"params.{key} is required")
    return value


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{str(k): str(v or "") for k, v in row.items()} for row in csv.DictReader(handle)]


def _iter_holding_paths(value: Any) -> Iterable[Path]:
    if isinstance(value, str):
        yield Path(value)
    else:
        for item in value or []:
            yield Path(str(item))


def fetch(context: BundleContext) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    holding_paths = list(_iter_holding_paths(_require(params, "holdings_csv_paths")))
    etf_scores = params.get("etf_scores") or {}
    if not isinstance(etf_scores, Mapping):
        raise StockEtfExposureError("params.etf_scores must be an object keyed by ETF ticker")
    holdings: list[dict[str, str]] = []
    for path in holding_paths:
        holdings.extend(_read_csv_rows(path))
    if not holdings:
        raise StockEtfExposureError("holdings_csv_paths produced zero rows")
    normalized_scores = {str(k).upper(): dict(v) for k, v in etf_scores.items() if isinstance(v, Mapping)}
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "bundle": BUNDLE,
        "holdings_csv_paths": [str(path) for path in holding_paths],
        "holding_rows": len(holdings),
        "etf_score_count": len(normalized_scores),
        "raw_persistence": "not_applicable; derived from saved etf_holding_snapshot CSV inputs",
        "fetched_at_utc": _now_utc(),
    }
    manifest_path = context.run_dir / "request_manifest.json"
    manifest_path.write_text(json.dumps(sanitize_value(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest_path)], {"etf_holding_snapshot_input": len(holdings)}, details=manifest), SourcePayload(holdings, normalized_scores)


def _float(value: Any, default: float = 0.0) -> float:
    text = str(value or "").replace("%", "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _style_tags(score: Mapping[str, Any], sector: str) -> list[str]:
    tags: list[str] = []
    raw = score.get("style_tags") or []
    if isinstance(raw, str):
        tags.extend([part.strip() for part in raw.replace(",", ";").split(";") if part.strip()])
    elif isinstance(raw, Iterable):
        tags.extend([str(part).strip() for part in raw if str(part).strip()])
    if sector:
        tags.append(sector.lower().replace(" ", "_"))
    return tags


def clean(context: BundleContext, payload: SourcePayload) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    available_time_et = str(_require(params, "available_time_et"))
    default_as_of_date = str(params.get("as_of_date") or "")
    grouped: dict[str, dict[str, Any]] = {}
    for holding in payload.holdings:
        symbol = str(holding.get("holding_ticker") or holding.get("symbol") or holding.get("ticker") or "").strip().upper()
        etf = str(holding.get("etf_ticker") or "").strip().upper()
        if not symbol or not etf:
            continue
        weight = _float(holding.get("weight")) / 100.0
        score = payload.etf_scores.get(etf, {})
        sector_score = _float(score.get("sector_score"), 1.0)
        theme_score = _float(score.get("theme_score"), 1.0)
        row = grouped.setdefault(symbol, {"symbol": symbol, "as_of_dates": [], "etfs": [], "weighted_total": 0.0, "weighted_sector": 0.0, "weighted_theme": 0.0, "top": ("", -1.0), "tags": [], "refs": []})
        row["as_of_dates"].append(str(holding.get("as_of_date") or default_as_of_date))
        row["etfs"].append(etf)
        row["weighted_total"] += weight
        row["weighted_sector"] += weight * sector_score
        row["weighted_theme"] += weight * theme_score
        if weight > row["top"][1]:
            row["top"] = (etf, weight)
        row["tags"].extend(_style_tags(score, str(holding.get("sector") or "")))
        as_of = str(holding.get("as_of_date") or default_as_of_date)
        row["refs"].append(f"{etf}:{as_of}" if as_of else etf)
    rows: list[dict[str, str]] = []
    for symbol in sorted(grouped):
        item = grouped[symbol]
        etfs = sorted(set(item["etfs"]))
        tags = sorted(set(item["tags"]))
        refs = sorted(set(item["refs"]))
        as_ofs = sorted({date for date in item["as_of_dates"] if date})
        rows.append({
            "as_of_date": as_ofs[-1] if as_ofs else default_as_of_date,
            "symbol": symbol,
            "exposed_etfs": ";".join(etfs),
            "top_exposure_etf": item["top"][0],
            "total_etf_exposure_score": _fmt(float(item["weighted_total"])),
            "weighted_sector_score": _fmt(float(item["weighted_sector"])),
            "weighted_theme_score": _fmt(float(item["weighted_theme"])),
            "style_tags": ";".join(tags),
            "source_etf_count": str(len(etfs)),
            "source_snapshot_refs": ";".join(refs),
            "available_time_et": available_time_et,
        })
    if not rows:
        raise StockEtfExposureError("zero stock_etf_exposure rows after cleaning")
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    output = context.cleaned_dir / "stock_etf_exposure.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    schema = context.cleaned_dir / "schema.json"
    schema.write_text(json.dumps({"stock_etf_exposure": FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(output), str(schema)], {"stock_etf_exposure": len(rows)}, details={"columns": FIELDS})


def save(context: BundleContext, clean_result: StepResult) -> StepResult:
    rows = [json.loads(line) for line in (context.cleaned_dir / "stock_etf_exposure.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / "stock_etf_exposure.csv"
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
