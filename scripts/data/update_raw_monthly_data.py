from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import ccxt

BUSINESS_TZ = 'America/New_York'
ROOT = Path(__file__).resolve().parents[2]

SPECS = [
    {
        'name': 'okx_candles_1m',
        'exchange': 'okx',
        'symbol': 'BTC/USDT:USDT',
        'kind': 'ohlcv',
        'timeframe': '1m',
        'out_dir': ROOT / 'data/raw/BTC-USDT-SWAP/candles',
    },
    {
        'name': 'bitget_funding',
        'exchange': 'bitget',
        'symbol': 'BTC/USDT:USDT',
        'kind': 'funding',
        'out_dir': ROOT / 'data/raw/BTCUSDT/funding',
    },
    {
        'name': 'bitget_basis_proxy_5m',
        'exchange': 'bitget',
        'symbol': 'BTC/USDT:USDT',
        'kind': 'ticker_snapshot_series',
        'field': 'basisProxy',
        'out_dir': ROOT / 'data/raw/BTCUSDT/basis_proxy',
    },
    {
        'name': 'bitget_index_price_5m',
        'exchange': 'bitget',
        'symbol': 'BTC/USDT:USDT',
        'kind': 'ticker_snapshot_series',
        'field': 'indexPrice',
        'out_dir': ROOT / 'data/raw/BTCUSDT/index_price',
    },
    {
        'name': 'bitget_mark_price_5m',
        'exchange': 'bitget',
        'symbol': 'BTC/USDT:USDT',
        'kind': 'ticker_snapshot_series',
        'field': 'markPrice',
        'out_dir': ROOT / 'data/raw/BTCUSDT/mark_price',
    },
]


def month_path(out_dir: Path, dt: datetime) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{dt.strftime('%Y-%m')}.jsonl"


def append_jsonl(path: Path, rows: list[dict]) -> int:
    if not rows:
        return 0
    existing = set()
    if path.exists():
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    existing.add(json.loads(line)['ts'])
                except Exception:
                    continue
    written = 0
    with path.open('a', encoding='utf-8') as f:
        for row in rows:
            if row['ts'] in existing:
                continue
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            written += 1
    return written


def current_month_range() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return start, end


def fetch_ohlcv_month(ex, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[dict]:
    since = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    rows = []
    while since < end_ms:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not batch:
            break
        for item in batch:
            ts = int(item[0])
            if ts >= end_ms:
                continue
            rows.append({
                'exchange': ex.id,
                'dataset': 'candles',
                'symbol': symbol,
                'ts': ts,
                'timestamp': datetime.fromtimestamp(ts / 1000, tz=UTC).isoformat(),
                'open': item[1],
                'high': item[2],
                'low': item[3],
                'close': item[4],
                'volume': item[5],
                'timeframe': timeframe,
            })
        next_since = int(batch[-1][0]) + 60_000
        if next_since <= since:
            break
        since = next_since
    return rows


def fetch_funding_month(ex, symbol: str, start: datetime, end: datetime) -> list[dict]:
    rows = ex.fetch_funding_rate_history(symbol, limit=1000)
    out = []
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    for row in rows:
        ts = int(row['timestamp'])
        if start_ms <= ts < end_ms:
            out.append({
                'exchange': ex.id,
                'dataset': 'funding_rate_history',
                'symbol': symbol,
                'ts': ts,
                'timestamp': row['datetime'],
                'fundingRate': row.get('fundingRate'),
                'info': row.get('info'),
            })
    return out


def fetch_ticker_snapshot(ex, symbol: str, field: str) -> dict | None:
    ticker = ex.fetch_ticker(symbol)
    ts = int(ticker['timestamp'])
    if field == 'basisProxy':
        mark = ticker.get('markPrice')
        index = ticker.get('indexPrice')
        if mark is None or index in (None, 0, '0', '0.0'):
            return None
        value = (float(mark) - float(index)) / float(index)
    else:
        value = ticker.get(field)
    if value is None:
        return None
    return {
        'exchange': ex.id,
        'dataset': field,
        'symbol': symbol,
        'ts': ts,
        'timestamp': ticker['datetime'],
        field: value,
        'info': ticker.get('info'),
    }


def main() -> None:
    start, end = current_month_range()
    print(json.dumps({'stage': 'month_range', 'start': start.isoformat(), 'end': end.isoformat()}, ensure_ascii=False))
    clients = {}
    for spec in SPECS:
        ex = clients.setdefault(spec['exchange'], getattr(ccxt, spec['exchange'])({'enableRateLimit': True}))
        out_path = month_path(spec['out_dir'], start)
        if spec['kind'] == 'ohlcv':
            rows = fetch_ohlcv_month(ex, spec['symbol'], spec['timeframe'], start, end)
            written = append_jsonl(out_path, rows)
        elif spec['kind'] == 'funding':
            rows = fetch_funding_month(ex, spec['symbol'], start, end)
            written = append_jsonl(out_path, rows)
        else:
            row = fetch_ticker_snapshot(ex, spec['symbol'], spec['field'])
            written = append_jsonl(out_path, [row] if row else [])
        print(json.dumps({'stage': 'updated', 'name': spec['name'], 'out': str(out_path), 'written': written}, ensure_ascii=False))


if __name__ == '__main__':
    main()
