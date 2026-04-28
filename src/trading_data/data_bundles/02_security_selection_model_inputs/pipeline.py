"""Manager-facing 02 SecuritySelectionModel input bundle."""
from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

from trading_data.data_bundles.config import config_section, load_bundle_config
from trading_data.data_bundles.model_input_bundle import BundleSpec, run_bundle

SPEC = BundleSpec(bundle="02_security_selection_model_inputs", model_id="security_selection_model", output_name="02_security_selection_model_inputs")

STOCK_ETF_EXPOSURE_FIELDS = [
    "as_of_date",
    "symbol",
    "exposed_etfs",
    "top_exposure_etf",
    "total_etf_exposure_score",
    "weighted_sector_score",
    "weighted_theme_score",
    "exposure_tags",
    "source_etf_count",
    "source_snapshot_refs",
    "available_time_et",
]


class SecuritySelectionInputsError(ValueError):
    """Raised for invalid SecuritySelectionModel input tasks."""


def run(task_key: dict[str, Any], *, run_id: str):
    prepared = deepcopy(task_key)
    params = prepared.setdefault("params", {})
    if "stock_etf_exposure" in params:
        output_root = str(prepared.get("output_root") or f"storage/{prepared.get('task_id', SPEC.bundle + '_task')}")
        derived_dir = Path(output_root) / "runs" / run_id / "derived" / "stock_etf_exposure"
        stock_path, _row_count = _derive_stock_etf_exposure(params["stock_etf_exposure"], output_dir=derived_dir)
        input_paths = params.setdefault("input_paths", {})
        input_paths["stock_etf_exposure"] = str(stock_path)
    return run_bundle(SPEC, prepared, run_id=run_id)


def _derive_stock_etf_exposure(params: Mapping[str, Any], *, output_dir: Path) -> tuple[Path, int]:
    """Build stock_etf_exposure as an internal Layer 02 pipeline step."""

    holding_paths = list(_iter_paths(_require_stock_etf_param(params, "holdings_csv_paths")))
    available_time_et = str(_require_stock_etf_param(params, "available_time_et"))
    default_as_of_date = str(params.get("as_of_date") or "")
    config_path = str(params.get("config_path") or "") or None
    config = load_bundle_config(SPEC.bundle, config_path=config_path)
    configured_scores = config_section(config, "stock_etf_exposure", "etf_scores")
    etf_scores = {**configured_scores, **dict(params.get("etf_scores") or {})}
    if not isinstance(etf_scores, Mapping):
        raise SecuritySelectionInputsError("params.stock_etf_exposure.etf_scores must be an object keyed by ETF ticker")

    holdings: list[dict[str, str]] = []
    for path in holding_paths:
        holdings.extend(_read_csv_rows(path))
    if not holdings:
        raise SecuritySelectionInputsError("params.stock_etf_exposure.holdings_csv_paths produced zero rows")
    normalized_scores = {str(k).upper(): dict(v) for k, v in etf_scores.items() if isinstance(v, Mapping)}

    grouped: dict[str, dict[str, Any]] = {}
    for holding in holdings:
        symbol = str(holding.get("holding_ticker") or holding.get("symbol") or holding.get("ticker") or "").strip().upper()
        etf = str(holding.get("etf_ticker") or "").strip().upper()
        if not symbol or not etf:
            continue
        weight = _float(holding.get("weight")) / 100.0
        score = normalized_scores.get(etf, {})
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
        row["tags"].extend(_exposure_tags(score, str(holding.get("sector_type") or "")))
        as_of = str(holding.get("as_of_date") or default_as_of_date)
        row["refs"].append(f"{etf}:{as_of}" if as_of else etf)

    rows: list[dict[str, str]] = []
    for symbol in sorted(grouped):
        item = grouped[symbol]
        as_ofs = sorted({date for date in item["as_of_dates"] if date})
        rows.append({
            "as_of_date": as_ofs[-1] if as_ofs else default_as_of_date,
            "symbol": symbol,
            "exposed_etfs": ";".join(sorted(set(item["etfs"]))),
            "top_exposure_etf": item["top"][0],
            "total_etf_exposure_score": _fmt(float(item["weighted_total"])),
            "weighted_sector_score": _fmt(float(item["weighted_sector"])),
            "weighted_theme_score": _fmt(float(item["weighted_theme"])),
            "exposure_tags": ";".join(sorted(set(item["tags"]))),
            "source_etf_count": str(len(set(item["etfs"]))),
            "source_snapshot_refs": ";".join(sorted(set(item["refs"]))),
            "available_time_et": available_time_et,
        })
    if not rows:
        raise SecuritySelectionInputsError("zero stock_etf_exposure rows after cleaning")

    cleaned_dir = output_dir / "cleaned"
    saved_dir = output_dir / "saved"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    saved_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = cleaned_dir / "stock_etf_exposure.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (cleaned_dir / "schema.json").write_text(json.dumps({"stock_etf_exposure": STOCK_ETF_EXPOSURE_FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = saved_dir / "stock_etf_exposure.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STOCK_ETF_EXPOSURE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return csv_path, len(rows)


def _require_stock_etf_param(params: Mapping[str, Any], key: str) -> Any:
    value = params.get(key)
    if value in (None, "", []):
        raise SecuritySelectionInputsError(f"params.stock_etf_exposure.{key} is required")
    return value


def _iter_paths(value: Any) -> Iterable[Path]:
    if isinstance(value, str):
        yield Path(value)
        return
    for item in value or []:
        yield Path(str(item))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{str(k): str(v or "") for k, v in row.items()} for row in csv.DictReader(handle)]


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


def _exposure_tags(score: Mapping[str, Any], sector_type: str) -> list[str]:
    tags: list[str] = []
    raw = score.get("exposure_tags") or []
    if isinstance(raw, str):
        tags.extend([part.strip() for part in raw.replace(",", ";").split(";") if part.strip()])
    elif isinstance(raw, Iterable):
        tags.extend([str(part).strip() for part in raw if str(part).strip()])
    if sector_type:
        tags.append(sector_type.lower().replace(" ", "_"))
    return tags
