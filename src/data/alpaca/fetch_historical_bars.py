from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[3]
BUSINESS_TZ = ZoneInfo("America/New_York")
BASE_URL = "https://data.alpaca.markets"


def parse_time_to_ms(value: str) -> int:
    value = value.strip()
    if value.isdigit():
        return int(value)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def ts_to_month_key(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).astimezone(BUSINESS_TZ)
    return dt.strftime("%Y-%m")


def yy_mm_dir_key(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).astimezone(BUSINESS_TZ)
    return dt.strftime("%y%m")


def month_file_path(base_dir: Path, ts_ms: int, dataset_name: str) -> Path:
    return base_dir / yy_mm_dir_key(ts_ms) / f"{dataset_name}.jsonl"


def load_existing_rows(path: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ts = row.get("ts")
            if ts is not None:
                out[int(ts)] = row
    return out


def load_month_store(base_dir: Path, *, dataset_name: str, resume: bool) -> dict[str, dict[int, dict[str, Any]]]:
    store: dict[str, dict[int, dict[str, Any]]] = {}
    if not resume or not base_dir.exists():
        return store
    for path in sorted(base_dir.glob(f"*/{dataset_name}.jsonl")):
        rows = load_existing_rows(path)
        if rows:
            store[path.parent.name] = rows
    return store


def flush_month_store(base_dir: Path, store: dict[str, dict[int, dict[str, Any]]], *, dataset_name: str) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    for month, rows in store.items():
        out_dir = base_dir / month
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{dataset_name}.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for ts in sorted(rows.keys()):
                f.write(json.dumps(rows[ts], ensure_ascii=False) + "\n")


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


def normalize_bar(*, asset_class: str, feed_scope: str, symbol: str, timeframe: str, row: dict[str, Any]) -> dict[str, Any]:
    ts = int(datetime.fromisoformat(row["t"].replace("Z", "+00:00")).timestamp() * 1000)
    return {
        "source": "alpaca",
        "asset_class": asset_class,
        "feed_scope": feed_scope,
        "dataset": "bars",
        "symbol": symbol,
        "timeframe": timeframe,
        "ts": ts,
        "timestamp": row["t"],
        "open": row.get("o"),
        "high": row.get("h"),
        "low": row.get("l"),
        "close": row.get("c"),
        "volume": row.get("v"),
        "trade_count": row.get("n"),
        "vwap": row.get("vw"),
    }


def default_output_dir(*, asset_class: str, symbol: str) -> Path:
    safe_symbol = symbol.replace("/", "-")
    return ROOT / "data" / safe_symbol


def fetch_historical_bars(*, asset_class: str, symbol: str, timeframe: str, start: str, end: str, limit: int, resume: bool, output_dir: Path | None) -> dict[str, Any]:
    if asset_class == "stocks":
        path = "/v2/stocks/bars"
        params = {
            "symbols": symbol,
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "limit": limit,
        }
        feed_scope = "stocks"
    elif asset_class == "crypto":
        path = "/v1beta3/crypto/us/bars"
        params = {
            "symbols": symbol,
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "limit": limit,
        }
        feed_scope = "crypto/us"
    else:
        raise ValueError(f"unsupported asset_class: {asset_class}")

    obj = request_json(path, params)
    rows = obj.get("bars", {}).get(symbol, [])
    out_dir = output_dir or default_output_dir(asset_class=asset_class, symbol=symbol)
    dataset_name = f"bars_{timeframe}"
    store = load_month_store(out_dir, dataset_name=dataset_name, resume=resume)
    kept = 0
    for raw in rows:
        row = normalize_bar(asset_class=asset_class, feed_scope=feed_scope, symbol=symbol, timeframe=timeframe, row=raw)
        month = yy_mm_dir_key(int(row["ts"]))
        store.setdefault(month, {})[int(row["ts"])] = row
        kept += 1
    flush_month_store(out_dir, store, dataset_name=dataset_name)
    return {
        "asset_class": asset_class,
        "symbol": symbol,
        "timeframe": timeframe,
        "output_dir": str(out_dir),
        "row_count": kept,
        "month_dirs": sorted(store.keys()),
        "next_page_token": obj.get("next_page_token"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Alpaca historical bars into monthly JSONL partitions.")
    parser.add_argument("--asset-class", choices=["stocks", "crypto"], required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = fetch_historical_bars(
        asset_class=args.asset_class,
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=args.start,
        end=args.end,
        limit=args.limit,
        resume=args.resume,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
