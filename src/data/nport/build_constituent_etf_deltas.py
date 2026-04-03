from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
HOLDINGS_ROOT = ROOT / 'context' / 'etf_holdings'
OUT_DIR = ROOT / 'context' / 'constituent_etf_deltas'


def load_json_or_markdown_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding='utf-8')
    if text.lstrip().startswith('{'):
        return json.loads(text)
    raise ValueError(f'file is not JSON-structured source: {path}')


def append_section(existing: str, section: str) -> str:
    if section.strip() in existing:
        return existing
    if existing and not existing.endswith('\n'):
        existing += '\n'
    return existing + '\n' + section.strip() + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description='Build or append a constituent -> ETF monthly delta/context file from month ETF holdings outputs.')
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--target-month', required=True)
    args = parser.parse_args()

    target_symbol = args.symbol.upper()
    yymm = args.target_month[2:4] + args.target_month[5:7]
    month_dir = HOLDINGS_ROOT / yymm
    matches = []

    for path in sorted(month_dir.glob(f'*_{yymm}.md')):
        try:
            payload = load_json_or_markdown_json(path)
        except Exception:
            continue
        etf_symbol = payload.get('etf_symbol')
        rows = payload.get('rows', [])
        for row in rows:
            constituent = str(row.get('constituent_symbol') or '').upper()
            name = str(row.get('constituent_name') or '')
            if constituent == target_symbol or name.upper() == target_symbol:
                matches.append({
                    'etf_symbol': etf_symbol,
                    'weight_percent': row.get('weight_percent'),
                    'constituent_name': row.get('constituent_name'),
                })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f'{target_symbol}.md'
    header = f'# {target_symbol} ETF context deltas\n\n'
    existing = out_path.read_text(encoding='utf-8') if out_path.exists() else header
    if not existing.startswith('# '):
        existing = header + existing

    section_lines = [
        f'## {args.target_month}',
        '',
    ]
    if matches:
        for item in matches:
            section_lines.append(
                f"- {item['etf_symbol']}: {item['weight_percent']}%"
            )
    else:
        section_lines.append('- no ETF holdings match found in prepared month ETF outputs')
    section = '\n'.join(section_lines)

    out_path.write_text(append_section(existing, section), encoding='utf-8')
    print(json.dumps({
        'symbol': target_symbol,
        'target_month': args.target_month,
        'matches': matches,
        'output': str(out_path),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
