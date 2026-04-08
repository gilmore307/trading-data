from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SIGNAL_CONTRACT_VERSION = 'v1'

ROOT = Path(__file__).resolve().parents[3]
PYTHON = 'python3'
from src.data.common.storage_paths import context_etf_aux_root, context_etf_holdings_root, context_signals_root

STATE_PATH = context_etf_aux_root() / 'state' / 'nport_state.json'
SIGNALS_DIR = context_signals_root()


def previous_month_key() -> str:
    now = datetime.now(UTC)
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1
    return f'{year:04d}-{month:02d}'


def validate_target_month(target_month: str) -> str:
    try:
        year_str, month_str = target_month.split('-', 1)
        year = int(year_str)
        month = int(month_str)
    except Exception as exc:
        raise ValueError(f'invalid target month: {target_month}') from exc
    if year < 1900 or month < 1 or month > 12:
        raise ValueError(f'invalid target month: {target_month}')
    return f'{year:04d}-{month:02d}'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def ensure_state_file(path: Path) -> dict[str, Any]:
    if path.exists():
        return load_json(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'target_month': None,
        'current_month_available': False,
        'current_month_captured': False,
        'updated_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
    }
    save_json(path, payload)
    return payload


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    ready_symbol_count = sum(1 for item in results if item.get('exists'))
    payload = {
        'kind': 'etf_holdings_ready',
        'source': 'trading-data',
        'pipeline': 'nport_month_retry',
        'target_month': target_month,
        'generated_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
        'contract_version': SIGNAL_CONTRACT_VERSION,
        'readiness': {
            'status': 'ready',
            'artifact_class': 'etf_holdings_month',
            'ready_for': ['trading-manager', 'trading-model'],
        },
        'artifacts': {
            'signal_scope': 'etf_holdings_month',
            'signal_path': str(signal_path),
            'context_root': str(context_etf_holdings_root()),
        },
        'results': results,
        'summary': {
            'symbol_count': len(results),
            'ready_symbol_count': ready_symbol_count,
            'failed_symbol_count': len(results) - ready_symbol_count,
        },
    }
    signal_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return signal_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Try once to acquire target-month ETF holdings via N-PORT; designed for repeated retry until success.')
    parser.add_argument('--state', type=Path, default=STATE_PATH)
    parser.add_argument('--tier', action='append', default=None)
    parser.add_argument('--symbol', action='append', default=None)
    parser.add_argument('--target-month', default=None)
    args = parser.parse_args()

    target_month = validate_target_month(args.target_month) if args.target_month else previous_month_key()
    state = ensure_state_file(args.state)
    state['target_month'] = target_month
    state['updated_at'] = datetime.now(UTC).isoformat().replace('+00:00', 'Z')
    save_json(args.state, state)

    run([PYTHON, 'src/data/nport/check_nport_availability.py', '--target-month', target_month])
    state = load_json(args.state)
    availability_status = (((state.get('source_reference') or {}).get('last_check_outcome') or {}).get('status'))
    if not state.get('current_month_available'):
        print(json.dumps({
            'target_month': target_month,
            'available': False,
            'status': availability_status or 'not_published_yet_retry_tomorrow'
        }, ensure_ascii=False, indent=2))
        return

    cmd = [PYTHON, 'src/data/nport/update_etf_holdings_from_nport.py', '--target-month', target_month]
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
        candidate_path = context_etf_holdings_root() / yy_mm / f'{symbol}_{yy_mm}.md'
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
