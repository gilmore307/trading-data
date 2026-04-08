from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SIGNAL_CONTRACT_VERSION = 'v1'

ROOT = Path(__file__).resolve().parents[3]
PYTHON = 'python3'
BUSINESS_TZ = ZoneInfo('America/New_York')
BATCHES_PATH = ROOT / 'config' / 'alpaca_monthly_batches.json'
SIGNALS_DIR = ROOT / 'context' / 'signals'


def _month_window_from_business_month(year: int, month: int) -> tuple[str, str, str]:
    first_local = datetime(year, month, 1, 0, 0, 0, tzinfo=BUSINESS_TZ)
    if month == 12:
        next_local = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=BUSINESS_TZ)
    else:
        next_local = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=BUSINESS_TZ)
    first_utc = first_local.astimezone(UTC)
    next_utc = next_local.astimezone(UTC)
    return (
        f'{year:04d}-{month:02d}',
        first_utc.isoformat().replace('+00:00', 'Z'),
        next_utc.isoformat().replace('+00:00', 'Z'),
    )


def previous_month_window() -> tuple[str, str, str]:
    now_local = datetime.now(BUSINESS_TZ)
    if now_local.month == 1:
        year, month = now_local.year - 1, 12
    else:
        year, month = now_local.year, now_local.month - 1
    return _month_window_from_business_month(year, month)


def month_window(target_month: str) -> tuple[str, str, str]:
    try:
        year_str, month_str = target_month.split('-', 1)
        year = int(year_str)
        month = int(month_str)
    except Exception as exc:
        raise ValueError(f'invalid target month: {target_month}') from exc
    if month < 1 or month > 12:
        raise ValueError(f'invalid target month: {target_month}')
    return _month_window_from_business_month(year, month)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _subprocess_env() -> dict[str, str]:
    import os

    env = os.environ.copy()
    existing = env.get('PYTHONPATH', '')
    root_str = str(ROOT)
    env['PYTHONPATH'] = f"{root_str}:{existing}" if existing else root_str
    return env


def run_symbol(symbol: str, asset_class: str, start: str, end: str) -> bool:
    env = _subprocess_env()
    cmd = [
        PYTHON,
        'src/data/alpaca/fetch_historical_bars.py',
        '--asset-class', asset_class,
        '--symbol', symbol,
        '--start', start,
        '--end', end,
        '--limit', '10000',
        '--resume',
    ]
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)

    for dataset_script in ['fetch_historical_quotes.py', 'fetch_historical_trades.py']:
        cmd = [
            PYTHON,
            f'src/data/alpaca/{dataset_script}',
            '--asset-class', asset_class,
            '--symbol', symbol,
            '--start', start,
            '--end', end,
            '--limit', '10000',
            '--resume',
        ]
        subprocess.run(cmd, cwd=ROOT, env=env, check=True)

    if asset_class == 'stocks':
        subprocess.run([
            PYTHON,
            'src/data/alpaca/fetch_news.py',
            '--symbol', symbol,
            '--start', start,
            '--end', end,
            '--limit', '50',
            '--resume',
        ], cwd=ROOT, env=env, check=False)
        subprocess.run([
            PYTHON,
            'src/data/alpaca/fetch_option_snapshots.py',
            '--underlying-symbol', symbol,
            '--limit', '100',
        ], cwd=ROOT, env=env, check=False)
    return True


def write_signal(*, batch_name: str, target_month: str, results: list[dict[str, Any]]) -> Path:
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    signal_path = SIGNALS_DIR / f'alpaca_month_ready_{batch_name}_{target_month}.json'
    ready_symbol_count = sum(1 for item in results if item.get('ok'))
    signal = {
        'kind': 'market_data_ready',
        'source': 'trading-data',
        'pipeline': 'alpaca_month_batch',
        'target_month': target_month,
        'generated_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
        'contract_version': SIGNAL_CONTRACT_VERSION,
        'readiness': {
            'status': 'ready',
            'artifact_class': 'market_data_month_batch',
            'ready_for': ['trading-manager', 'trading-model'],
        },
        'artifacts': {
            'signal_scope': 'market_data_month',
            'signal_batch': batch_name,
            'signal_path': str(signal_path),
            'month_root': str(ROOT / 'data'),
        },
        'results': results,
        'summary': {
            'batch_name': batch_name,
            'symbol_count': len(results),
            'ready_symbol_count': ready_symbol_count,
            'failed_symbol_count': len(results) - ready_symbol_count,
        },
    }
    signal_path.write_text(json.dumps(signal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return signal_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Backfill Alpaca market data for a target month using a configured batch.')
    parser.add_argument('--batch', required=True)
    parser.add_argument('--config', type=Path, default=BATCHES_PATH)
    parser.add_argument('--target-month', default=None)
    args = parser.parse_args()

    payload = load_json(args.config)
    batch = payload['batches'].get(args.batch)
    if not batch:
        raise ValueError(f'unknown batch: {args.batch}')

    if args.target_month:
        target_month, start, end = month_window(args.target_month)
    else:
        target_month, start, end = previous_month_window()
    results = []
    for item in batch:
        symbol = item['symbol']
        asset_class = item['asset_class']
        ok = False
        error = None
        try:
            run_symbol(symbol, asset_class, start, end)
            ok = True
        except Exception as exc:
            error = str(exc)
        results.append({
            'symbol': symbol,
            'asset_class': asset_class,
            'ok': ok,
            'error': error,
        })

    signal_path = write_signal(batch_name=args.batch, target_month=target_month, results=results)
    print(json.dumps({
        'batch': args.batch,
        'target_month': target_month,
        'results': results,
        'signal_path': str(signal_path),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
