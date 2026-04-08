from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = 'https://data.alpaca.markets'


def load_dotenv() -> None:
    env_path = ROOT / '.env'
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def auth_headers() -> dict[str, str]:
    key = os.getenv('APCA_API_KEY_ID') or os.getenv('ALPACA_API_KEY_ID')
    secret = os.getenv('APCA_API_SECRET_KEY') or os.getenv('ALPACA_API_SECRET_KEY')
    headers = {'accept': 'application/json'}
    if key and secret:
        headers['APCA-API-KEY-ID'] = key
        headers['APCA-API-SECRET-KEY'] = secret
    return headers


def next_month(target_month: str) -> str:
    year_str, month_str = target_month.split('-', 1)
    year = int(year_str)
    month = int(month_str)
    if month == 12:
        return f'{year + 1:04d}-01'
    return f'{year:04d}-{month + 1:02d}'


def month_range(start_month: str, end_month: str) -> list[str]:
    out: list[str] = []
    current = start_month
    while current <= end_month:
        out.append(current)
        current = next_month(current)
    return out


def probe_month(*, symbol: str, asset_class: str, target_month: str) -> dict[str, Any]:
    start = f'{target_month}-01T00:00:00Z'
    end = f'{next_month(target_month)}-01T00:00:00Z' if False else f'{next_month(target_month)}-01T00:00:00Z'
    if asset_class == 'stocks':
        path = '/v2/stocks/bars'
        params = {'symbols': symbol, 'timeframe': '1Day', 'start': start, 'end': end, 'limit': 1}
        row_key = 'bars'
    elif asset_class == 'crypto':
        path = '/v1beta3/crypto/us/bars'
        params = {'symbols': symbol, 'timeframe': '1Day', 'start': start, 'end': end, 'limit': 1}
        row_key = 'bars'
    else:
        raise ValueError(f'unsupported asset_class: {asset_class}')
    response = requests.get(f'{BASE_URL}{path}', params=params, headers=auth_headers(), timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get(row_key, {}).get(symbol, []) if isinstance(payload, dict) else []
    return {
        'target_month': target_month,
        'row_count': len(rows),
        'first_timestamp': rows[0].get('t') if rows else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Detect the earliest complete month currently available for a symbol via Alpaca historical data.')
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--asset-class', required=True, choices=['stocks', 'crypto'])
    parser.add_argument('--probe-start-month', default='2014-01')
    parser.add_argument('--probe-end-month', default=None)
    args = parser.parse_args()

    load_dotenv()
    now = datetime.now(UTC)
    default_end = f'{now.year:04d}-{now.month:02d}'
    probe_end_month = args.probe_end_month or default_end

    probes = []
    earliest = None
    for month in month_range(args.probe_start_month, probe_end_month):
        result = probe_month(symbol=args.symbol, asset_class=args.asset_class, target_month=month)
        probes.append(result)
        if result['row_count'] > 0:
            earliest = month
            break

    print(json.dumps({
        'symbol': args.symbol,
        'asset_class': args.asset_class,
        'earliest_complete_month': earliest,
        'probe_start_month': args.probe_start_month,
        'probe_end_month': probe_end_month,
        'probes': probes,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
