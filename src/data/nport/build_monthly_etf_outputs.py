from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
TARGETS_PATH = ROOT / 'config' / 'etf_holdings_target_universe.json'
HOLDINGS_ROOT = ROOT / 'context' / 'etf_holdings'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def flatten_tiers(payload: dict[str, Any], tiers: list[str] | None) -> list[str]:
    selected = tiers or list(payload['tiers'].keys())
    out = []
    seen = set()
    for tier in selected:
        for symbol in payload['tiers'].get(tier, []):
            if symbol not in seen:
                seen.add(symbol)
                out.append(symbol)
    return out


def render_markdown(payload: dict[str, Any], target_month: str) -> str:
    rows = payload.get('rows', [])
    etf_symbol = payload.get('etf_symbol')
    lines = [
        f'# {etf_symbol} {target_month} ETF holdings',
        '',
        f'- etf_symbol: {etf_symbol}',
        f'- target_month: {target_month}',
        f'- row_count: {len(rows)}',
        '',
        '## constituents',
        '',
        '| constituent_symbol | constituent_name | weight_percent |',
        '| --- | --- | ---: |',
    ]
    for row in rows:
        lines.append(
            f"| {row.get('constituent_symbol','')} | {row.get('constituent_name','')} | {row.get('weight_percent','')} |"
        )
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='Build month-partitioned ETF holdings markdown outputs from extracted N-PORT candidate files.')
    parser.add_argument('--target-month', required=True)
    parser.add_argument('--targets', type=Path, default=TARGETS_PATH)
    parser.add_argument('--tier', action='append', default=None)
    parser.add_argument('--symbol', action='append', default=None)
    args = parser.parse_args()

    yymm = args.target_month[2:4] + args.target_month[5:7]
    target_payload = load_json(args.targets)
    symbols = flatten_tiers(target_payload, args.tier)
    if args.symbol:
        allowed = set(args.symbol)
        symbols = [s for s in symbols if s in allowed]

    out_dir = HOLDINGS_ROOT / yymm
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for symbol in symbols:
        source_path = out_dir / f'{symbol}_{yymm}.md'
        if not source_path.exists():
            results.append({'symbol': symbol, 'ok': False, 'reason': 'missing_extracted_source'})
            continue
        try:
            payload = load_json(source_path)
            markdown = render_markdown(payload, args.target_month)
            source_path.write_text(markdown + '\n', encoding='utf-8')
            results.append({'symbol': symbol, 'ok': True, 'path': str(source_path)})
        except Exception as exc:
            results.append({'symbol': symbol, 'ok': False, 'reason': str(exc)})

    print(json.dumps({'target_month': args.target_month, 'results': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
