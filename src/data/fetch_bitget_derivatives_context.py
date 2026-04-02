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

BASE_URL = 'https://api.bitget.com'
DEFAULT_SYMBOL = 'BTCUSDT'
DEFAULT_PRODUCT_TYPE = 'USDT-FUTURES'
DEFAULT_START = '2022-09-01T00:00:00Z'
BUSINESS_TZ = ZoneInfo('America/New_York')
TIMEFRAME_MS = {
    '1m': 60_000,
    '5m': 300_000,
    '15m': 900_000,
    '1h': 3_600_000,
    '4h': 14_400_000,
    '1d': 86_400_000,
}


def parse_time_to_ms(value: str) -> int:
    value = value.strip()
    if value.isdigit():
        return int(value)
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def ts_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000, tz=UTC).isoformat()


def ts_to_month_key(ts: int) -> str:
    dt = datetime.fromtimestamp(ts / 1000, tz=UTC).astimezone(BUSINESS_TZ)
    return dt.strftime('%Y-%m')


def dataset_dir(dataset: str, *, symbol: str) -> Path:
    return Path('data/raw') / symbol / dataset


def month_file_path(base_dir: Path, ts: int) -> Path:
    return base_dir / f'{ts_to_month_key(ts)}.jsonl'


def load_existing_rows(path: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return out
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ts = row.get('ts')
            if ts is not None:
                out[int(ts)] = row
    return out


def write_jsonl(rows_by_ts: dict[int, dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for ts in sorted(rows_by_ts.keys()):
            f.write(json.dumps(rows_by_ts[ts], ensure_ascii=False) + '\n')


def load_month_store(base_dir: Path, *, resume: bool) -> tuple[dict[str, dict[int, dict[str, Any]]], int | None, int | None]:
    store: dict[str, dict[int, dict[str, Any]]] = {}
    oldest = None
    newest = None
    if not resume or not base_dir.exists():
        return store, oldest, newest
    for path in sorted(base_dir.glob('*.jsonl')):
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


def flush_month_store(base_dir: Path, store: dict[str, dict[int, dict[str, Any]]]) -> None:
    for month, rows in store.items():
        write_jsonl(rows, base_dir / f'{month}.jsonl')


def get_json(path: str, params: dict[str, Any], *, timeout: int = 30, max_retries: int = 10) -> dict[str, Any]:
    backoff = 1.5
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(BASE_URL + path, params=params, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            if data.get('code') != '00000':
                raise RuntimeError(json.dumps(data, ensure_ascii=False))
            return data
        except Exception:
            if attempt == max_retries:
                raise
            sleep_for = backoff + random.uniform(0, 0.8)
            time.sleep(sleep_for)
            backoff = min(backoff * 1.7, 30.0)
    raise RuntimeError('unreachable')


def normalize_candle_row(row: list[str], *, dataset: str, symbol: str, product_type: str, timeframe: str) -> tuple[int, dict[str, Any]]:
    ts = int(row[0])
    payload = {
        'exchange': 'bitget',
        'dataset': dataset,
        'symbol': symbol,
        'productType': product_type,
        'timeframe': timeframe,
        'ts': ts,
        'timestamp': ts_to_iso(ts),
        'open': float(row[1]),
        'high': float(row[2]),
        'low': float(row[3]),
        'close': float(row[4]),
        'baseVolume': None if row[5] in (None, '0', 0) else float(row[5]),
        'quoteVolume': None if row[6] in (None, '0', 0) else float(row[6]),
    }
    return ts, payload


def fetch_candles_range(*, symbol: str, product_type: str, dataset: str, endpoint: str, timeframe: str, range_start_ms: int, range_end_ms: int | None, limit: int, sleep_seconds: float, store: dict[str, dict[int, dict[str, Any]]], flush_every: int = 20, output_dir: Path | None = None, progress_label: str | None = None) -> int:
    window_ms = TIMEFRAME_MS[timeframe] * limit
    cursor = range_start_ms
    rounds = 0
    hard_end = range_end_ms or 2**63 - 1
    while cursor <= hard_end:
        params = {
            'symbol': symbol,
            'productType': product_type,
            'granularity': timeframe,
            'limit': str(limit),
            'startTime': str(cursor),
        }
        if range_end_ms is not None:
            request_end = min(cursor + window_ms - TIMEFRAME_MS[timeframe], range_end_ms)
            if request_end <= cursor:
                break
            params['endTime'] = str(request_end)
        data = get_json(endpoint, params)
        rows = data.get('data') or []
        if not rows:
            break
        rounds += 1
        max_seen = None
        for row in rows:
            ts, payload = normalize_candle_row(row, dataset=dataset, symbol=symbol, product_type=product_type, timeframe=timeframe)
            if ts < range_start_ms:
                continue
            if range_end_ms is not None and ts > range_end_ms:
                continue
            month = ts_to_month_key(ts)
            store.setdefault(month, {})[ts] = payload
            max_seen = ts if max_seen is None else max(max_seen, ts)
        if output_dir and rounds % flush_every == 0:
            flush_month_store(output_dir, store)
            total_rows = sum(len(x) for x in store.values())
            all_ts = [ts for month_rows in store.values() for ts in month_rows.keys()]
            print(json.dumps({'event': progress_label or f'{dataset}_progress', 'rounds': rounds, 'stored_rows': total_rows, 'stored_oldest': ts_to_iso(min(all_ts)) if all_ts else None, 'stored_newest': ts_to_iso(max(all_ts)) if all_ts else None}, ensure_ascii=False))
        if max_seen is None:
            cursor += window_ms
        else:
            cursor = max_seen + TIMEFRAME_MS[timeframe]
        time.sleep(sleep_seconds)
    return rounds


def fetch_candles(*, symbol: str, product_type: str, dataset: str, endpoint: str, timeframe: str, start_ms: int, end_ms: int | None, limit: int, sleep_seconds: float, resume: bool, backfill: bool) -> dict[str, Any]:
    out_dir = dataset_dir(dataset, symbol=symbol)
    store, oldest_ts, newest_ts = load_month_store(out_dir, resume=resume)
    rounds = 0

    if newest_ts is not None:
        latest_start = max(start_ms, newest_ts + TIMEFRAME_MS[timeframe])
        if latest_start <= (end_ms or 2**63 - 1):
            rounds += fetch_candles_range(symbol=symbol, product_type=product_type, dataset=dataset, endpoint=endpoint, timeframe=timeframe, range_start_ms=latest_start, range_end_ms=end_ms, limit=limit, sleep_seconds=sleep_seconds, store=store, output_dir=out_dir, progress_label=f'{dataset}_forward_progress')

        if backfill and oldest_ts is not None:
            earliest_end = min((end_ms if end_ms is not None else oldest_ts - TIMEFRAME_MS[timeframe]), oldest_ts - TIMEFRAME_MS[timeframe])
            if start_ms <= earliest_end:
                rounds += fetch_candles_range(symbol=symbol, product_type=product_type, dataset=dataset, endpoint=endpoint, timeframe=timeframe, range_start_ms=start_ms, range_end_ms=earliest_end, limit=limit, sleep_seconds=sleep_seconds, store=store, output_dir=out_dir, progress_label=f'{dataset}_backfill_progress')
    else:
        rounds += fetch_candles_range(symbol=symbol, product_type=product_type, dataset=dataset, endpoint=endpoint, timeframe=timeframe, range_start_ms=start_ms, range_end_ms=end_ms, limit=limit, sleep_seconds=sleep_seconds, store=store, output_dir=out_dir, progress_label=f'{dataset}_progress')

    flush_month_store(out_dir, store)
    total_rows = sum(len(x) for x in store.values())
    return {'output_dir': str(out_dir), 'rows': total_rows, 'months': len(store), 'rounds': rounds}


def fetch_funding(*, symbol: str, product_type: str, start_ms: int, sleep_seconds: float, resume: bool) -> dict[str, Any]:
    out_dir = dataset_dir('funding', symbol=symbol)
    store, _, _ = load_month_store(out_dir, resume=resume)
    page = 1
    rounds = 0
    while True:
        data = get_json('/api/v2/mix/market/history-fund-rate', {
            'symbol': symbol,
            'productType': product_type,
            'pageSize': '100',
            'pageNo': str(page),
        })
        rows = data.get('data') or []
        if not rows:
            break
        rounds += 1
        for row in rows:
            ts = int(row['fundingTime'])
            if ts < start_ms:
                continue
            payload = {
                'exchange': 'bitget',
                'dataset': 'funding_rate_history',
                'symbol': symbol,
                'productType': product_type,
                'ts': ts,
                'timestamp': ts_to_iso(ts),
                'fundingRate': float(row['fundingRate']),
            }
            month = ts_to_month_key(ts)
            store.setdefault(month, {})[ts] = payload
        if rounds % 10 == 0:
            flush_month_store(out_dir, store)
        oldest_in_page = min(int(r['fundingTime']) for r in rows)
        if oldest_in_page < start_ms:
            break
        page += 1
        time.sleep(sleep_seconds)
    flush_month_store(out_dir, store)
    total_rows = sum(len(x) for x in store.values())
    return {'output_dir': str(out_dir), 'rows': total_rows, 'months': len(store), 'rounds': rounds}


def load_all_month_rows(base_dir: Path) -> dict[int, dict[str, Any]]:
    store, _, _ = load_month_store(base_dir, resume=True)
    merged: dict[int, dict[str, Any]] = {}
    for month_rows in store.values():
        merged.update(month_rows)
    return merged


def build_basis_proxy(*, symbol: str, product_type: str, timeframe: str) -> dict[str, Any]:
    mark_rows = load_all_month_rows(dataset_dir('mark_price', symbol=symbol))
    index_rows = load_all_month_rows(dataset_dir('index_price', symbol=symbol))
    out_dir = dataset_dir('basis_proxy', symbol=symbol)
    store: dict[str, dict[int, dict[str, Any]]] = {}
    for ts, mark in mark_rows.items():
        idx = index_rows.get(ts)
        if not idx:
            continue
        index_close = idx['close']
        mark_close = mark['close']
        basis_pct = None if not index_close else (mark_close - index_close) / index_close
        payload = {
            'exchange': 'bitget',
            'dataset': 'basis_proxy',
            'symbol': symbol,
            'productType': product_type,
            'timeframe': timeframe,
            'ts': ts,
            'timestamp': mark['timestamp'],
            'markClose': mark_close,
            'indexClose': index_close,
            'basisPct': basis_pct,
        }
        month = ts_to_month_key(ts)
        store.setdefault(month, {})[ts] = payload
    flush_month_store(out_dir, store)
    total_rows = sum(len(x) for x in store.values())
    return {'output_dir': str(out_dir), 'rows': total_rows, 'months': len(store)}


def main() -> None:
    parser = argparse.ArgumentParser(description='Fetch Bitget derivatives context directly into monthly JSONL partitions.')
    parser.add_argument('--symbol', default=DEFAULT_SYMBOL)
    parser.add_argument('--product-type', default=DEFAULT_PRODUCT_TYPE)
    parser.add_argument('--kind', choices=['candles', 'funding', 'mark', 'index', 'basis-proxy', 'all'], default='all')
    parser.add_argument('--timeframe', default='5m')
    parser.add_argument('--start', default=DEFAULT_START)
    parser.add_argument('--end', default=None)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--sleep-seconds', type=float, default=0.25)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--backfill', action='store_true', help='When resuming candles, also fill older history before the current earliest stored row.')
    args = parser.parse_args()

    start_ms = parse_time_to_ms(args.start)
    end_ms = parse_time_to_ms(args.end) if args.end else None
    summary: dict[str, Any] = {'symbol': args.symbol, 'productType': args.product_type, 'timeframe': args.timeframe, 'start': args.start, 'end': args.end}

    if args.kind in {'candles', 'all'}:
        summary['candles'] = fetch_candles(symbol=args.symbol, product_type=args.product_type, dataset='candles', endpoint='/api/v2/mix/market/history-candles', timeframe=args.timeframe, start_ms=start_ms, end_ms=end_ms, limit=args.limit, sleep_seconds=args.sleep_seconds, resume=args.resume, backfill=args.backfill)
    if args.kind in {'mark', 'all'}:
        summary['mark_price'] = fetch_candles(symbol=args.symbol, product_type=args.product_type, dataset='mark_price', endpoint='/api/v2/mix/market/history-mark-candles', timeframe=args.timeframe, start_ms=start_ms, end_ms=end_ms, limit=args.limit, sleep_seconds=args.sleep_seconds, resume=args.resume, backfill=args.backfill)
    if args.kind in {'index', 'all'}:
        summary['index_price'] = fetch_candles(symbol=args.symbol, product_type=args.product_type, dataset='index_price', endpoint='/api/v2/mix/market/history-index-candles', timeframe=args.timeframe, start_ms=start_ms, end_ms=end_ms, limit=args.limit, sleep_seconds=args.sleep_seconds, resume=args.resume, backfill=args.backfill)
    if args.kind in {'funding', 'all'}:
        summary['funding'] = fetch_funding(symbol=args.symbol, product_type=args.product_type, start_ms=start_ms, sleep_seconds=args.sleep_seconds, resume=args.resume)
    if args.kind in {'basis-proxy', 'all'}:
        summary['basis_proxy'] = build_basis_proxy(symbol=args.symbol, product_type=args.product_type, timeframe=args.timeframe)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
