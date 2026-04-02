from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[3]
BUSINESS_TZ = ZoneInfo("America/New_York")
BASE_URL = "https://data.alpaca.markets"


def yy_mm_dir_key(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).astimezone(BUSINESS_TZ)
    return dt.strftime("%y%m")


def auth_headers() -> dict[str, str]:
    key = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")
    headers = {"accept": "application/json"}
    if key and secret:
        headers["APCA-API-KEY-ID"] = key
        headers["APCA-API-SECRET-KEY"] = secret
    return headers


def request_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{BASE_URL}{path}?{urlencode(params, doseq=True)}"
    resp = requests.get(url, headers=auth_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def normalize_snapshot(*, underlying_symbol: str, option_symbol: str, row: dict[str, Any]) -> dict[str, Any]:
    ts_source = None
    for key_path in [
        ("latestTrade", "t"),
        ("latestQuote", "t"),
        ("minuteBar", "t"),
        ("dailyBar", "t"),
        ("prevDailyBar", "t"),
    ]:
        outer, inner = key_path
        if isinstance(row.get(outer), dict) and row[outer].get(inner):
            ts_source = row[outer][inner]
            break
    if ts_source is None:
        ts = int(datetime.now(UTC).timestamp() * 1000)
        iso_ts = datetime.fromtimestamp(ts / 1000, tz=UTC).isoformat()
    else:
        ts = int(datetime.fromisoformat(ts_source.replace("Z", "+00:00")).timestamp() * 1000)
        iso_ts = ts_source
    return {
        "source": "alpaca",
        "dataset": "options_snapshot",
        "underlying_symbol": underlying_symbol,
        "option_symbol": option_symbol,
        "ts": ts,
        "timestamp": iso_ts,
        "snapshot": row,
    }


def fetch_option_snapshots(*, underlying_symbol: str, limit: int, output_dir: Path | None) -> dict[str, Any]:
    obj = request_json(f"/v1beta1/options/snapshots/{underlying_symbol}", {"limit": limit})
    snapshots = obj.get("snapshots", {})
    out_dir = output_dir or (ROOT / "data" / underlying_symbol)
    count = 0
    months: set[str] = set()
    for option_symbol, payload in snapshots.items():
        row = normalize_snapshot(underlying_symbol=underlying_symbol, option_symbol=option_symbol, row=payload)
        month = yy_mm_dir_key(int(row["ts"]))
        months.add(month)
        month_dir = out_dir / month
        month_dir.mkdir(parents=True, exist_ok=True)
        out = month_dir / "options_snapshots.jsonl"
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        count += 1
    return {
        "underlying_symbol": underlying_symbol,
        "output_dir": str(out_dir),
        "row_count": count,
        "month_dirs": sorted(months),
        "next_page_token": obj.get("next_page_token"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Alpaca option snapshots into symbol/month JSONL partitions.")
    parser.add_argument("--underlying-symbol", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = fetch_option_snapshots(
        underlying_symbol=args.underlying_symbol,
        limit=args.limit,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
