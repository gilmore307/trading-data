#!/usr/bin/env python3
"""Fetch reviewed ETF-universe holdings and combine them for equity pool input."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Any

DEFAULT_UNIVERSE_CSV = Path("/root/projects/trading-storage/main/shared/layer_01_02_market_context_etf_universe.csv")
DEFAULT_OUTPUT_ROOT = Path("/root/projects/trading-storage/storage/01_source_data/realtime/etf_universe_holdings")
DEFAULT_RECEIPT_ROOT = Path("/root/projects/trading-storage/storage/02_control_plane/runtime/equity_total_symbol_pool")
DEFAULT_MODEL_LAYER = "layer_02_sector_context"

_ETF_HOLDINGS_MODULE = import_module("data_feed.06_feed_etf_holdings.pipeline")
_run_feed = _ETF_HOLDINGS_MODULE.run
OUTPUT_FIELDS = list(_ETF_HOLDINGS_MODULE.FIELDS)


@dataclass(frozen=True)
class EtfSpec:
    symbol: str
    issuer_name: str
    model_layer: str
    universe_type: str


def _read_universe(path: Path, *, model_layers: set[str] | None) -> list[EtfSpec]:
    specs: list[EtfSpec] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            symbol = str(row.get("symbol") or "").strip().upper()
            issuer_name = str(row.get("issuer_name") or "").strip()
            model_layer = str(row.get("model_layer") or "").strip()
            if not symbol or not issuer_name:
                continue
            if model_layers is not None and model_layer not in model_layers:
                continue
            specs.append(
                EtfSpec(
                    symbol=symbol,
                    issuer_name=issuer_name,
                    model_layer=model_layer,
                    universe_type=str(row.get("universe_type") or "").strip(),
                )
            )
    specs.sort(key=lambda item: item.symbol)
    return specs


def _manager_controls(etf_count: int) -> dict[str, Any]:
    return {
        "allow_live_provider_calls": True,
        "realtime_provider_maintenance": True,
        "allowed_providers": ["etf_issuer_holdings"],
        "allowed_endpoint_families": ["holdings_file"],
        "max_requests": max(etf_count * 2, 1),
        "max_symbols": max(etf_count, 1),
        "timeout_seconds": 30,
        "retry_policy_ref": "single_bounded_issuer_request",
        "rate_limit_policy_ref": "serial_etf_issuer_requests",
    }


def _clean_symbol(value: str) -> str:
    symbol = value.strip().upper()
    for prefix in ("NASDAQ:", "NYSE:", "AMEX:"):
        symbol = symbol.removeprefix(prefix)
    return symbol


def _is_equity_holding(row: dict[str, str]) -> bool:
    symbol = _clean_symbol(row.get("holding_symbol", ""))
    if not symbol or symbol in {"-", "--", "USD", "CASH"}:
        return False
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,10}", symbol):
        return False
    asset_class = str(row.get("asset_class") or "").strip().lower()
    if not asset_class:
        return True
    blocked = ("cash", "currency", "bond", "treasury", "future", "swap", "option")
    if any(token in asset_class for token in blocked):
        return False
    return any(token in asset_class for token in ("equity", "stock", "common"))


def _read_feed_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{str(key): str(value or "") for key, value in row.items()} for row in csv.DictReader(handle)]


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def collect_holdings(
    *,
    universe_csv: Path,
    output_root: Path,
    as_of_date: str,
    model_layers: set[str] | None,
    allow_partial: bool,
    run_id_prefix: str = "equity_total_pool",
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    specs = _read_universe(universe_csv, model_layers=model_layers)
    rows_by_key: dict[tuple[str, str], dict[str, str]] = {}
    results: list[dict[str, Any]] = []
    controls = _manager_controls(len(specs))

    for spec in specs:
        run_id = f"{run_id_prefix}_{as_of_date}_{spec.symbol.lower()}".replace("-", "")
        task_output_root = output_root / as_of_date / "feed_runs" / spec.symbol
        task_key = {
            "task_id": f"equity_total_symbol_pool_etf_holdings_{spec.symbol.lower()}",
            "feed": "06_feed_etf_holdings",
            "params": {
                "etf_symbol": spec.symbol,
                "issuer_name": spec.issuer_name,
                "as_of_date": as_of_date,
            },
            "manager_controls": controls,
            "output_root": str(task_output_root),
        }
        result = _run_feed(task_key, run_id=run_id)
        entry = {
            "etf": asdict(spec),
            "status": result.status,
            "row_counts": dict(result.row_counts),
            "references": list(result.references),
            "details": dict(result.details),
        }
        results.append(entry)
        if result.status != "succeeded":
            if not allow_partial:
                raise RuntimeError(f"ETF holdings fetch failed for {spec.symbol}: {entry['details']}")
            continue
        saved = task_output_root / "runs" / run_id / "saved" / "etf_holding_snapshot.csv"
        for row in _read_feed_rows(saved):
            row["holding_symbol"] = _clean_symbol(row.get("holding_symbol", ""))
            if not _is_equity_holding(row):
                continue
            key = (row.get("etf_symbol", "").upper(), row["holding_symbol"])
            rows_by_key.setdefault(key, {field: row.get(field, "") for field in OUTPUT_FIELDS})

    rows = sorted(rows_by_key.values(), key=lambda row: (row["holding_symbol"], row["etf_symbol"]))
    receipt = {
        "contract_type": "etf_universe_holdings_collection_receipt",
        "as_of_date": as_of_date,
        "universe_csv": str(universe_csv),
        "model_layers": sorted(model_layers) if model_layers is not None else "all",
        "requested_etf_count": len(specs),
        "succeeded_etf_count": sum(1 for item in results if item["status"] == "succeeded"),
        "failed_etf_count": sum(1 for item in results if item["status"] != "succeeded"),
        "selected_holding_row_count": len(rows),
        "allow_partial": allow_partial,
        "etf_results": results,
        "boundary_note": "Official issuer ETF holdings are collected for equity-total-pool source input only; this performs no broker/account/model activation.",
    }
    return rows, receipt


def write_outputs(rows: list[dict[str, str]], *, output_csv: Path, receipt_path: Path, receipt: dict[str, Any]) -> None:
    _write_rows(output_csv, rows)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**receipt, "output_csv": str(output_csv)}
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-csv", type=Path, default=DEFAULT_UNIVERSE_CSV)
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--model-layer", action="append", default=[DEFAULT_MODEL_LAYER])
    parser.add_argument("--all-model-layers", action="store_true")
    parser.add_argument("--allow-partial", action="store_true", default=True)
    parser.add_argument("--fail-on-partial", action="store_false", dest="allow_partial")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--receipt-root", type=Path, default=DEFAULT_RECEIPT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model_layers = None if args.all_model_layers else {str(item) for item in args.model_layer}
    output_csv = args.output_root / args.as_of_date / "etf_universe_holdings.csv"
    receipt_path = args.receipt_root / "etf_universe_holdings_receipt.json"
    rows, receipt = collect_holdings(
        universe_csv=args.universe_csv,
        output_root=args.output_root,
        as_of_date=args.as_of_date,
        model_layers=model_layers,
        allow_partial=args.allow_partial,
    )
    write_outputs(rows, output_csv=output_csv, receipt_path=receipt_path, receipt=receipt)
    print(json.dumps({**receipt, "output_csv": str(output_csv)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
