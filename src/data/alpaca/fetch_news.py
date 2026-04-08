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
            key = row.get("id")
            if key is not None:
                out[int(key)] = row
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
            for key in sorted(rows.keys()):
                f.write(json.dumps(rows[key], ensure_ascii=False) + "\n")


def auth_headers() -> dict[str, str]:
    key = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")
    headers = {"accept": "application/json"}
    if key and secret:
        headers["APCA-API-KEY-ID"] = key
        headers["APCA-API-SECRET-KEY"] = secret
    return headers


def request_json_response(path: str, params: dict[str, Any]) -> requests.Response:
    url = f"{BASE_URL}{path}?{urlencode(params, doseq=True)}"
    return requests.get(url, headers=auth_headers(), timeout=30)


def normalize_news(row: dict[str, Any]) -> dict[str, Any]:
    ts = int(datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).timestamp() * 1000)
    timestamp_et = datetime.fromtimestamp(ts / 1000, tz=UTC).astimezone(BUSINESS_TZ).isoformat()
    return {
        "source": "alpaca",
        "dataset": "news",
        "id": row.get("id"),
        "ts": ts,
        "timestamp": timestamp_et,
        "updated_at": row.get("updated_at"),
        "headline": row.get("headline"),
        "summary": row.get("summary"),
        "author": row.get("author"),
        "source_name": row.get("source"),
        "symbols": row.get("symbols"),
        "url": row.get("url"),
    }


def default_output_dir(*, symbol: str) -> Path:
    return ROOT.parent / 'trading-storage' / '1_ingest' / '1_long_retention' / '4_news' / symbol


def _candidate_params(symbol: str, start: str, end: str, limit: int) -> list[dict[str, Any]]:
    start_date = start.split("T")[0]
    end_date = end.split("T")[0]
    if start_date == end_date:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_date = start_dt.date().fromordinal(start_dt.date().toordinal() + 1).isoformat()
    return [
        {"symbols": symbol, "start": start_date, "end": end_date, "limit": limit},
        {"symbols": symbol, "start": start, "end": end, "limit": limit},
        {"symbols": symbol, "limit": limit},
    ]


def fetch_news(*, symbol: str, start: str, end: str, limit: int, resume: bool, output_dir: Path | None) -> dict[str, Any]:
    out_dir = output_dir or default_output_dir(symbol=symbol)
    dataset_name = "news"
    store = load_month_store(out_dir, dataset_name=dataset_name, resume=resume)

    obj = None
    chosen_params = None
    last_error_text = None
    for params in _candidate_params(symbol, start, end, limit):
        resp = request_json_response("/v1beta1/news", params)
        if resp.ok:
            obj = resp.json()
            chosen_params = dict(params)
            break
        last_error_text = resp.text[:500]

    if obj is None or chosen_params is None:
        raise requests.HTTPError(f"news request failed for symbol={symbol}: {last_error_text}")

    kept = 0
    page_count = 0
    next_page_token = None
    while True:
        params = dict(chosen_params)
        if next_page_token:
            params["page_token"] = next_page_token
        resp = request_json_response("/v1beta1/news", params)
        resp.raise_for_status()
        obj = resp.json()
        rows = obj.get("news", [])
        page_count += 1
        for raw in rows:
            row = normalize_news(raw)
            month = yy_mm_dir_key(int(row["ts"]))
            store.setdefault(month, {})[int(row["id"])] = row
            kept += 1
        next_page_token = obj.get("next_page_token")
        if not next_page_token:
            break

    flush_month_store(out_dir, store, dataset_name=dataset_name)
    return {
        "symbol": symbol,
        "output_dir": str(out_dir),
        "row_count": kept,
        "month_dirs": sorted(store.keys()),
        "page_count": page_count,
        "next_page_token": next_page_token,
        "complete": next_page_token is None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Alpaca news into symbol/month JSONL partitions.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    result = fetch_news(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        limit=args.limit,
        resume=args.resume,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
