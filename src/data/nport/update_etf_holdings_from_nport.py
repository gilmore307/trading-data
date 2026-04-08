from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PYTHON = 'python3'
TARGETS_PATH = ROOT / 'config' / 'etf_holdings_target_universe.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def run(cmd: list[str], required: bool = True) -> bool:
    print(json.dumps({'run': cmd, 'required': required}, ensure_ascii=False))
    try:
        subprocess.run(cmd, cwd=ROOT, check=True)
        return True
    except subprocess.CalledProcessError:
        if required:
            raise
        return False


def flatten_tiers(payload: dict[str, Any], tiers: list[str] | None) -> list[str]:
    all_tiers = payload['tiers']
    selected_names = tiers or list(all_tiers.keys())
    out = []
    seen = set()
    for tier_name in selected_names:
        for symbol in all_tiers.get(tier_name, []):
            if symbol not in seen:
                seen.add(symbol)
                out.append(symbol)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description='Run the N-PORT ETF holdings pipeline for the configured priority ETF target universe.')
    parser.add_argument('--targets', type=Path, default=TARGETS_PATH)
    parser.add_argument('--tier', action='append', default=None, help='Limit to one or more tier names from etf_holdings_target_universe.json')
    parser.add_argument('--symbol', action='append', default=None, help='Limit further to one or more ETF symbols')
    parser.add_argument('--target-month', default='2026-03')
    args = parser.parse_args()

    target_payload = load_json(args.targets)
    symbols = flatten_tiers(target_payload, args.tier)
    if args.symbol:
        allowed = set(args.symbol)
        symbols = [s for s in symbols if s in allowed]

    run([PYTHON, 'src/data/nport/discover_nport_dataset.py'])
    run([PYTHON, 'src/data/nport/download_nport_metadata.py', '--max-bytes', '500000000'])
    run([PYTHON, 'src/data/nport/map_etf_to_sec_series.py'])

    results = []
    for symbol in symbols:
        ok = run([
            PYTHON,
            'src/data/nport/extract_series_holdings_from_nport.py',
            '--etf-symbol', symbol,
            '--target-month', args.target_month,
        ], required=False)
        results.append({'symbol': symbol, 'ok': ok})

    extra_args = [
        *sum([['--tier', t] for t in (args.tier or [])], []),
        *sum([['--symbol', s] for s in (args.symbol or [])], []),
    ]

    run([
        PYTHON,
        'src/data/nport/build_monthly_etf_outputs.py',
        '--target-month', args.target_month,
        *extra_args,
    ], required=False)

    run([
        PYTHON,
        'src/data/nport/build_monthly_output_manifest.py',
        '--target-month', args.target_month,
        *extra_args,
    ], required=False)

    run([
        PYTHON,
        '--target-month', args.target_month,
        *extra_args,
    ], required=False)

    print(json.dumps({'symbols': symbols, 'results': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
