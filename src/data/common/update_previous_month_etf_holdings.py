from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PYTHON = 'python3'
STATE_PATH = ROOT / 'context' / 'etf_holdings' / '_aux' / 'state' / 'nport_state.json'
SIGNALS_DIR = ROOT / 'context' / 'signals'


def previous_month_key() -> str:
    now = datetime.now(UTC)
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1
    return f'{year:04d}-{month:02d}'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(cmd: list[str], required: bool = True) -> bool:
    try:
        subprocess.run(cmd, cwd=ROOT, check=True)
        return True
    except subprocess.CalledProcessError:
        if required:
            raise
        return False


def write_signal(*, target_month: str, results: list[dict[str, Any]]) -> Path:
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    signal_path = SIGNALS_DIR / f'etf_holdings_ready_{target_month}.json'
    payload = {
        'kind': 'etf_holdings_ready',
        'source': 'trading-data',
        'pipeline': 'nport_previous_month_retry',
        'target_month': target_month,
        'generated_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
        'results': results,
        'downstream_hint': {
            'consumer': 'trading-model',
            'action': 'start_context_validation_and_model_tests',
            'reason': 'previous_month_etf_holdings_ready'
        }
    }
    signal_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return signal_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Try once to acquire previous-month ETF holdings via N-PORT; designed for daily retry until success.')
    parser.add_argument('--state', type=Path, default=STATE_PATH)
    parser.add_argument('--tier', action='append', default=None)
    parser.add_argument('--symbol', action='append', default=None)
    args = parser.parse_args()

    target_month = previous_month_key()
    state = load_json(args.state)
    state['target_month'] = target_month
    save_json(args.state, state)

    run([PYTHON, 'src/data/common/check_nport_availability.py', '--target-month', target_month])
    state = load_json(args.state)
    if not state.get('current_month_available'):
        print(json.dumps({
            'target_month': target_month,
            'available': False,
            'status': 'not_published_yet_retry_tomorrow'
        }, ensure_ascii=False, indent=2))
        return

    cmd = [PYTHON, 'src/data/common/update_etf_holdings_from_nport.py', '--target-month', target_month]
    for tier in args.tier or []:
        cmd += ['--tier', tier]
    for symbol in args.symbol or []:
        cmd += ['--symbol', symbol]
    run(cmd)

    selected_symbols = args.symbol or []
    if not selected_symbols and args.tier:
        targets = load_json(ROOT / 'config' / 'etf_holdings_target_universe.json')
        seen = set()
        for tier_name in args.tier:
            for symbol in targets.get('tiers', {}).get(tier_name, []):
                if symbol not in seen:
                    seen.add(symbol)
                    selected_symbols.append(symbol)

    results = []
    for symbol in selected_symbols:
        yy_mm = target_month[2:4] + target_month[5:7]
        candidate_path = ROOT / 'context' / 'etf_holdings' / yy_mm / f'{symbol}_{yy_mm}.md'
        results.append({'symbol': symbol, 'exists': candidate_path.exists(), 'path': str(candidate_path)})

    state = load_json(args.state)
    state['current_month_captured'] = True
    save_json(args.state, state)
    signal_path = write_signal(target_month=target_month, results=results)
    print(json.dumps({
        'target_month': target_month,
        'available': True,
        'captured': True,
        'signal_path': str(signal_path),
        'results': results,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
