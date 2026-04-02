from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PYTHON = 'python3'
BATCHES_PATH = ROOT / 'config' / 'alpaca_monthly_batches.json'
SIGNALS_DIR = ROOT / 'context' / 'signals'


def previous_month_window() -> tuple[str, str, str]:
    now = datetime.now(UTC)
    first_this_month = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 1:
        first_prev_month = datetime(now.year - 1, 12, 1, tzinfo=UTC)
    else:
        first_prev_month = datetime(now.year, now.month - 1, 1, tzinfo=UTC)
    return (
        first_prev_month.strftime('%Y-%m'),
        first_prev_month.isoformat().replace('+00:00', 'Z'),
        first_this_month.isoformat().replace('+00:00', 'Z'),
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def run_symbol(symbol: str, asset_class: str, start: str, end: str) -> bool:
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
    subprocess.run(cmd, cwd=ROOT, check=True)

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
        subprocess.run(cmd, cwd=ROOT, check=True)

    if asset_class == 'stocks':
        subprocess.run([
            PYTHON,
            'src/data/alpaca/fetch_news.py',
            '--symbol', symbol,
            '--start', start,
            '--end', end,
            '--limit', '50',
            '--resume',
        ], cwd=ROOT, check=False)
        subprocess.run([
            PYTHON,
            'src/data/alpaca/fetch_option_snapshots.py',
            '--underlying-symbol', symbol,
            '--limit', '100',
        ], cwd=ROOT, check=False)
    return True


def write_signal(*, batch_name: str, target_month: str, results: list[dict[str, Any]]) -> Path:
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    signal_path = SIGNALS_DIR / f'alpaca_previous_month_ready_{batch_name}_{target_month}.json'
    signal = {
        'kind': 'market_data_ready',
        'source': 'trading-data',
        'pipeline': 'alpaca_previous_month_batch',
        'batch_name': batch_name,
        'target_month': target_month,
        'generated_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
        'results': results,
        'downstream_hint': {
            'consumer': 'trading-model',
            'action': 'start_data_validation_and_model_tests',
            'reason': 'previous_month_market_data_batch_finished'
        }
    }
    signal_path.write_text(json.dumps(signal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return signal_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Backfill Alpaca market data for the previous completed month using a configured batch.')
    parser.add_argument('--batch', required=True)
    parser.add_argument('--config', type=Path, default=BATCHES_PATH)
    args = parser.parse_args()

    payload = load_json(args.config)
    batch = payload['batches'].get(args.batch)
    if not batch:
        raise ValueError(f'unknown batch: {args.batch}')

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
