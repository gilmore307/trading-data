"""Internal stock ETF exposure derivation for SecuritySelectionModel inputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from trading_data.data_bundles.config import config_section, load_bundle_config

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


class StockEtfExposureError(ValueError):
    """Raised for invalid stock ETF exposure derivation inputs."""


def _require(params: Mapping[str, Any], key: str) -> Any:
    value = params.get(key)
    if value in (None, "", []):
        raise StockEtfExposureError(f"params.stock_etf_exposure.{key} is required")
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


def derive(params: Mapping[str, Any], *, output_dir: Path) -> tuple[Path, int]:
    """Build saved/cleaned stock_etf_exposure artifacts and return CSV path/count."""

    holding_paths = list(_iter_paths(_require(params, "holdings_csv_paths")))
    available_time_et = str(_require(params, "available_time_et"))
    default_as_of_date = str(params.get("as_of_date") or "")
    config_path = str(params.get("config_path") or "") or None
    config = load_bundle_config("02_security_selection_model_inputs", config_path=config_path)
    configured_scores = config_section(config, "stock_etf_exposure", "etf_scores")
    etf_scores = {**configured_scores, **dict(params.get("etf_scores") or {})}
    if not isinstance(etf_scores, Mapping):
        raise StockEtfExposureError("params.stock_etf_exposure.etf_scores must be an object keyed by ETF ticker")

    holdings: list[dict[str, str]] = []
    for path in holding_paths:
        holdings.extend(_read_csv_rows(path))
    if not holdings:
        raise StockEtfExposureError("holdings_csv_paths produced zero rows")
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
        row["tags"].extend(_style_tags(score, str(holding.get("sector") or "")))
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
            "style_tags": ";".join(sorted(set(item["tags"]))),
            "source_etf_count": str(len(set(item["etfs"]))),
            "source_snapshot_refs": ";".join(sorted(set(item["refs"]))),
            "available_time_et": available_time_et,
        })
    if not rows:
        raise StockEtfExposureError("zero stock_etf_exposure rows after cleaning")

    cleaned_dir = output_dir / "cleaned"
    saved_dir = output_dir / "saved"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    saved_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = cleaned_dir / "stock_etf_exposure.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (cleaned_dir / "schema.json").write_text(json.dumps({"stock_etf_exposure": FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = saved_dir / "stock_etf_exposure.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return csv_path, len(rows)
