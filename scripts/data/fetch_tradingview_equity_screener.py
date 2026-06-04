#!/usr/bin/env python3
"""Fetch a bounded TradingView US equity screener snapshot."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_ROOT = Path("/root/projects/trading-storage/storage/01_source_data/realtime/tradingview_equity_screener")
DEFAULT_RECEIPT_ROOT = Path("/root/projects/trading-storage/storage/02_control_plane/runtime/equity_total_symbol_pool")
SCANNER_URL = "https://scanner.tradingview.com/america/scan"
SCANNER_COLUMNS = [
    "name",
    "description",
    "type",
    "subtype",
    "exchange",
    "sector",
    "close",
    "volume",
    "Value.Traded",
    "market_cap_basic",
]
OUTPUT_FIELDS = [
    "Symbol",
    "Name",
    "Sector",
    "Last Price",
    "Volume",
    "Dollar Volume",
    "Market Cap",
    "Exchange",
    "TradingView Symbol",
    "TradingView Type",
    "TradingView Subtype",
    "Included By",
    "As Of Date",
]


def _scanner_payload(*, sort_by: str, limit: int) -> dict[str, Any]:
    return {
        "markets": ["america"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": SCANNER_COLUMNS,
        "filter": [
            {"left": "type", "operation": "equal", "right": "stock"},
            {"left": "subtype", "operation": "equal", "right": "common"},
            {"left": "exchange", "operation": "in_range", "right": ["NASDAQ", "NYSE", "AMEX"]},
        ],
        "sort": {"sortBy": sort_by, "sortOrder": "desc"},
        "range": [0, limit],
        "options": {"lang": "en"},
    }


def _post_scan(payload: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(
        SCANNER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "OpenClaw trading-data research snapshot",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"TradingView scanner request failed: {exc}") from exc


def _clean_symbol(value: str) -> str:
    symbol = value.upper().strip()
    for prefix in ("NASDAQ:", "NYSE:", "AMEX:"):
        symbol = symbol.removeprefix(prefix)
    return symbol


def fetch_rows(*, per_rank_limit: int, timeout_seconds: float, as_of_date: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    merged: dict[str, dict[str, str]] = {}
    scan_receipts: list[dict[str, Any]] = []
    rank_specs = {
        "dollar_volume_top": "Value.Traded",
        "market_cap_top": "market_cap_basic",
    }

    for source_reason, sort_by in rank_specs.items():
        payload = _scanner_payload(sort_by=sort_by, limit=per_rank_limit)
        response = _post_scan(payload, timeout_seconds=timeout_seconds)
        data = response.get("data") or []
        scan_receipts.append(
            {
                "source_reason": source_reason,
                "sort_by": sort_by,
                "requested_limit": per_rank_limit,
                "returned_count": len(data),
                "total_count": response.get("totalCount"),
            }
        )
        for item in data:
            values = item.get("d") or []
            if len(values) != len(SCANNER_COLUMNS):
                continue
            raw = dict(zip(SCANNER_COLUMNS, values, strict=True))
            symbol = _clean_symbol(str(raw.get("name") or item.get("s") or ""))
            if not symbol:
                continue
            row = merged.setdefault(
                symbol,
                {
                    "Symbol": symbol,
                    "Name": str(raw.get("description") or ""),
                    "Sector": str(raw.get("sector") or ""),
                    "Last Price": "",
                    "Volume": "",
                    "Dollar Volume": "",
                    "Market Cap": "",
                    "Exchange": str(raw.get("exchange") or ""),
                    "TradingView Symbol": str(item.get("s") or ""),
                    "TradingView Type": str(raw.get("type") or ""),
                    "TradingView Subtype": str(raw.get("subtype") or ""),
                    "Included By": "",
                    "As Of Date": as_of_date,
                },
            )
            row["Last Price"] = str(raw.get("close") or row["Last Price"] or "")
            row["Volume"] = str(raw.get("volume") or row["Volume"] or "")
            row["Dollar Volume"] = str(raw.get("Value.Traded") or row["Dollar Volume"] or "")
            row["Market Cap"] = str(raw.get("market_cap_basic") or row["Market Cap"] or "")
            included_by = {part for part in row["Included By"].split(";") if part}
            included_by.add(source_reason)
            row["Included By"] = ";".join(sorted(included_by))

    rows = sorted(merged.values(), key=lambda row: row["Symbol"])
    receipt = {
        "contract_type": "tradingview_equity_screener_snapshot_receipt",
        "as_of_date": as_of_date,
        "scanner_url": SCANNER_URL,
        "per_rank_limit": per_rank_limit,
        "scan_receipts": scan_receipts,
        "selected_symbol_count": len(rows),
        "boundary_note": "Bounded no-login TradingView screener snapshot for realtime equity-total-pool input, ranked by traded dollar value and market cap; it performs no broker/account/model activation and must not be used as historical replay candidate evidence.",
    }
    return rows, receipt


def write_outputs(rows: list[dict[str, str]], *, output_csv: Path, receipt_path: Path, receipt: dict[str, Any]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps({**receipt, "output_csv": str(output_csv)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-rank-limit", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--receipt-root", type=Path, default=DEFAULT_RECEIPT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_csv = args.output_root / args.as_of_date / "tradingview_equity_screener.csv"
    receipt_path = args.receipt_root / "tradingview_equity_screener_receipt.json"
    rows, receipt = fetch_rows(
        per_rank_limit=args.per_rank_limit,
        timeout_seconds=args.timeout_seconds,
        as_of_date=args.as_of_date,
    )
    write_outputs(rows, output_csv=output_csv, receipt_path=receipt_path, receipt=receipt)
    print(json.dumps({**receipt, "output_csv": str(output_csv)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
