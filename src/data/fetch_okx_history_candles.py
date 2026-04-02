from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests
from requests import HTTPError

OKX_HISTORY_CANDLES_URL = "https://www.okx.com/api/v5/market/history-candles"
DEFAULT_SLEEP_SECONDS = 0.12
DEFAULT_LIMIT = 100
DEFAULT_INST_ID = "BTC-USDT"
DEFAULT_BAR = "1m"
BUSINESS_TZ = ZoneInfo("America/New_York")


def parse_time_to_ms(value: str) -> int:
    value = value.strip()
    if value.isdigit():
        return int(value)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def ts_to_month_key(ts: int) -> str:
    dt = datetime.fromtimestamp(ts / 1000, tz=UTC).astimezone(BUSINESS_TZ)
    return dt.strftime("%Y-%m")


def default_output_dir(*, inst_id: str, dataset: str) -> Path:
    safe_inst = inst_id.replace("/", "-")
    return Path("data/raw") / safe_inst / dataset


def month_file_path(base_dir: Path, ts: int) -> Path:
    return base_dir / f"{ts_to_month_key(ts)}.jsonl"


def fetch_page(*, inst_id: str, bar: str, limit: int, after: int | None = None, timeout: int = 20) -> list[list[str]]:
    params = {
        "instId": inst_id,
        "bar": bar,
        "limit": str(limit),
    }
    if after is not None:
        params["after"] = str(after)
    resp = requests.get(OKX_HISTORY_CANDLES_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "0":
        raise RuntimeError(f"OKX error: {data}")
    rows = data.get("data", [])
    if not isinstance(rows, list):
        raise RuntimeError(f"unexpected OKX payload: {data}")
    return rows


def fetch_page_with_retry(*, inst_id: str, bar: str, limit: int, after: int | None = None, max_retries: int = 12) -> list[list[str]]:
    backoff = 2.0
    for attempt in range(1, max_retries + 1):
        try:
            return fetch_page(inst_id=inst_id, bar=bar, limit=limit, after=after)
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status != 429 or attempt == max_retries:
                raise
            sleep_for = backoff + random.uniform(0, 0.8)
            print(json.dumps({
                "event": "retry",
                "reason": "http_429",
                "attempt": attempt,
                "sleep_seconds": round(sleep_for, 2),
                "instId": inst_id,
                "bar": bar,
                "after": after,
            }, ensure_ascii=False))
            time.sleep(sleep_for)
            backoff = min(backoff * 1.8, 60.0)
        except requests.RequestException:
            if attempt == max_retries:
                raise
            sleep_for = backoff + random.uniform(0, 0.8)
            print(json.dumps({
                "event": "retry",
                "reason": "request_exception",
                "attempt": attempt,
                "sleep_seconds": round(sleep_for, 2),
                "instId": inst_id,
                "bar": bar,
                "after": after,
            }, ensure_ascii=False))
            time.sleep(sleep_for)
            backoff = min(backoff * 1.8, 60.0)
    raise RuntimeError("unreachable")


def normalize_row(row: list[str], *, inst_id: str, bar: str) -> dict[str, Any]:
    ts = int(row[0])
    return {
        "exchange": "okx",
        "endpoint": "history-candles",
        "instId": inst_id,
        "bar": bar,
        "ts": ts,
        "timestamp": datetime.fromtimestamp(ts / 1000, tz=UTC).isoformat(),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "vol": float(row[5]),
        "volCcy": float(row[6]),
        "volCcyQuote": float(row[7]),
        "confirm": int(row[8]),
    }


def load_existing_rows(path: Path) -> dict[int, dict[str, Any]]:
    existing: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return existing
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            existing[int(row["ts"])] = row
    return existing


def write_jsonl(rows_by_ts: dict[int, dict[str, Any]], path: Path, *, only_confirmed: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for ts in sorted(rows_by_ts.keys()):
            row = rows_by_ts[ts]
            if only_confirmed and int(row.get("confirm", 0)) != 1:
                continue
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_month_store(base_dir: Path, *, resume: bool) -> tuple[dict[str, dict[int, dict[str, Any]]], int | None, int | None]:
    store: dict[str, dict[int, dict[str, Any]]] = {}
    oldest = None
    newest = None
    if not resume or not base_dir.exists():
        return store, oldest, newest
    for path in sorted(base_dir.glob("*.jsonl")):
        rows = load_existing_rows(path)
        if not rows:
            continue
        month = path.stem
        store[month] = rows
        month_oldest = min(rows)
        month_newest = max(rows)
        oldest = month_oldest if oldest is None else min(oldest, month_oldest)
        newest = month_newest if newest is None else max(newest, month_newest)
    return store, oldest, newest


def flush_month_store(base_dir: Path, store: dict[str, dict[int, dict[str, Any]]], *, only_confirmed: bool) -> None:
    for month, rows in store.items():
        write_jsonl(rows, base_dir / f"{month}.jsonl", only_confirmed=only_confirmed)


def fetch_history_range(
    *,
    inst_id: str,
    bar: str,
    limit: int,
    sleep_seconds: float,
    start_ms: int | None,
    end_ms: int | None,
    max_pages: int | None,
    store: dict[str, dict[int, dict[str, Any]]],
    existing_oldest_ts: int | None,
    progress_every: int,
    checkpoint_every: int,
    output_dir: Path,
) -> tuple[dict[str, dict[int, dict[str, Any]]], int]:
    after: int | None = end_ms
    pages = 0
    if existing_oldest_ts is not None:
        after = existing_oldest_ts
    while True:
        if max_pages is not None and pages >= max_pages:
            break
        rows = fetch_page_with_retry(inst_id=inst_id, bar=bar, limit=limit, after=after)
        if not rows:
            break
        pages += 1
        min_ts = min(int(r[0]) for r in rows)
        max_ts = max(int(r[0]) for r in rows)
        kept = 0
        for raw in rows:
            normalized = normalize_row(raw, inst_id=inst_id, bar=bar)
            ts = int(normalized["ts"])
            if end_ms is not None and ts > end_ms:
                continue
            if start_ms is not None and ts < start_ms:
                continue
            month = ts_to_month_key(ts)
            store.setdefault(month, {})[ts] = normalized
            kept += 1
        if pages % checkpoint_every == 0:
            flush_month_store(output_dir, store, only_confirmed=True)
        if pages % progress_every == 0:
            all_ts = [ts for month_rows in store.values() for ts in month_rows.keys()]
            oldest = min(all_ts) if all_ts else None
            newest = max(all_ts) if all_ts else None
            print(json.dumps({
                "event": "progress",
                "pages": pages,
                "page_oldest": min_ts,
                "page_newest": max_ts,
                "kept_in_page": kept,
                "stored_rows": len(all_ts),
                "stored_oldest": None if oldest is None else datetime.fromtimestamp(oldest / 1000, tz=UTC).isoformat(),
                "stored_newest": None if newest is None else datetime.fromtimestamp(newest / 1000, tz=UTC).isoformat(),
            }, ensure_ascii=False))
        if start_ms is not None and min_ts < start_ms:
            break
        after = min_ts
        time.sleep(sleep_seconds)
    return store, pages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch OKX historical candles directly into monthly JSONL partitions.")
    parser.add_argument("--inst-id", default=DEFAULT_INST_ID)
    parser.add_argument("--bar", default=DEFAULT_BAR)
    parser.add_argument("--pages", type=int, default=None, help="Optional page cap. Omit for unbounded until start is reached.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--include-unconfirmed", action="store_true")
    parser.add_argument("--start", type=str, default=None, help="Inclusive start time (ISO8601 or ms).")
    parser.add_argument("--end", type=str, default=None, help="Inclusive end time (ISO8601 or ms). Defaults to latest available.")
    parser.add_argument("--resume", action="store_true", help="Load and extend existing monthly output files.")
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--checkpoint-every", type=int, default=25, help="Write partial progress every N pages.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output_dir = args.output_dir or default_output_dir(inst_id=args.inst_id, dataset="candles")
    start_ms = None if args.start is None else parse_time_to_ms(args.start)
    end_ms = None if args.end is None else parse_time_to_ms(args.end)
    store, existing_oldest_ts, _ = load_month_store(output_dir, resume=args.resume)
    store, pages = fetch_history_range(
        inst_id=args.inst_id,
        bar=args.bar,
        limit=args.limit,
        sleep_seconds=args.sleep_seconds,
        start_ms=start_ms,
        end_ms=end_ms,
        max_pages=args.pages,
        store=store,
        existing_oldest_ts=existing_oldest_ts,
        progress_every=max(1, args.progress_every),
        checkpoint_every=max(1, args.checkpoint_every),
        output_dir=output_dir,
    )
    flush_month_store(output_dir, store, only_confirmed=not args.include_unconfirmed)
    all_rows = [row for month_rows in store.values() for row in month_rows.values()]
    all_rows.sort(key=lambda row: int(row["ts"]))
    print(json.dumps({
        "output_dir": str(output_dir),
        "row_count": len(all_rows),
        "month_count": len(store),
        "first": None if not all_rows else all_rows[0]["timestamp"],
        "last": None if not all_rows else all_rows[-1]["timestamp"],
        "instId": args.inst_id,
        "bar": args.bar,
        "pages": pages,
        "start": args.start,
        "end": args.end,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
