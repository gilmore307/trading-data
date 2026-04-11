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

from src.data.common.month_meta_utils import load_effective_meta
from src.data.common.storage_paths import market_tape_options_snapshots_root

ROOT = Path(__file__).resolve().parents[3]
BUSINESS_TZ = ZoneInfo("America/New_York")
BASE_URL = "https://data.alpaca.markets"


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


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
        "asset_class": "stocks",
    }


def load_existing_rows(path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    out: dict[tuple[str, int], dict[str, Any]] = {}
    if not path.exists():
        return out
    meta = load_effective_meta(path)
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            merged = dict(meta)
            merged.update(row)
            option_symbol = merged.get("option_symbol")
            ts = merged.get("ts")
            if option_symbol and ts is not None:
                out[(str(option_symbol), int(ts))] = merged
    return out


def load_month_store(base_dir: Path, *, dataset_name: str, resume: bool) -> dict[str, dict[tuple[str, int], dict[str, Any]]]:
    store: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    if not resume or not base_dir.exists():
        return store
    for path in sorted(base_dir.glob(f"*/{dataset_name}.jsonl")):
        rows = load_existing_rows(path)
        if rows:
            store[path.parent.name] = rows
    return store


def flush_month_store(base_dir: Path, store: dict[str, dict[tuple[str, int], dict[str, Any]]], *, dataset_name: str) -> None:
    if not store:
        return
    for month, rows in store.items():
        if not rows:
            continue
        out_dir = base_dir / month
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{dataset_name}.jsonl"
        ordered_rows = sorted(rows.values(), key=lambda item: (int(item.get("ts", 0)), str(item.get("option_symbol", ""))))
        with out.open("w", encoding="utf-8") as f:
            for row in ordered_rows:
                compact = {
                    "option_symbol": row.get("option_symbol"),
                    "ts": row.get("ts"),
                    "timestamp": row.get("timestamp"),
                    "snapshot": row.get("snapshot"),
                }
                f.write(json.dumps(compact, ensure_ascii=False) + "\n")


def fetch_option_snapshots(*, underlying_symbol: str, limit: int, output_dir: Path | None, resume: bool) -> dict[str, Any]:
    obj = request_json(f"/v1beta1/options/snapshots/{underlying_symbol}", {"limit": limit})
    snapshots = obj.get("snapshots", {})
    out_dir = output_dir or (market_tape_options_snapshots_root(symbol=underlying_symbol) / underlying_symbol.replace("/", "-"))
    store = load_month_store(out_dir, dataset_name="options_snapshots", resume=resume)
    count = 0
    months: set[str] = set()
    for option_symbol, payload in snapshots.items():
        row = normalize_snapshot(underlying_symbol=underlying_symbol, option_symbol=option_symbol, row=payload)
        month = yy_mm_dir_key(int(row["ts"]))
        months.add(month)
        store.setdefault(month, {})[(str(row["option_symbol"]), int(row["ts"]))] = row
        count += 1
    flush_month_store(out_dir, store, dataset_name="options_snapshots")
    return {
        "underlying_symbol": underlying_symbol,
        "output_dir": str(out_dir),
        "row_count": count,
        "month_dirs": sorted(set(store.keys()) | months),
        "next_page_token": obj.get("next_page_token"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Alpaca option snapshots into symbol/month JSONL partitions.")
    parser.add_argument("--underlying-symbol", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    result = fetch_option_snapshots(
        underlying_symbol=args.underlying_symbol,
        limit=args.limit,
        output_dir=args.output_dir,
        resume=args.resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
