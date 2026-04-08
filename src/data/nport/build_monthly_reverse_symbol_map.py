from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
from src.data.common.storage_paths import context_etf_holdings_root

HOLDINGS_ROOT = context_etf_holdings_root()
TARGETS_PATH = ROOT / 'config' / 'etf_holdings_target_universe.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def flatten_tiers(payload: dict[str, Any], tiers: list[str] | None) -> list[str]:
    selected = tiers or list(payload['tiers'].keys())
    out: list[str] = []
    seen: set[str] = set()
    for tier in selected:
        for symbol in payload['tiers'].get(tier, []):
            if symbol not in seen:
                seen.add(symbol)
                out.append(symbol)
    return out


def safe_weight(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(str(value))
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description='Build a month-level reverse holdings map from ETF outputs to underlying stock symbols.')
    parser.add_argument('--target-month', required=True)
    parser.add_argument('--targets', type=Path, default=TARGETS_PATH)
    parser.add_argument('--tier', action='append', default=None)
    parser.add_argument('--symbol', action='append', default=None)
    args = parser.parse_args()

    yymm = args.target_month[2:4] + args.target_month[5:7]
    month_dir = HOLDINGS_ROOT / yymm
    month_dir.mkdir(parents=True, exist_ok=True)

    target_payload = load_json(args.targets)
    etf_symbols = flatten_tiers(target_payload, args.tier)
    if args.symbol:
        allowed = set(args.symbol)
        etf_symbols = [s for s in etf_symbols if s in allowed]

    reverse_map: dict[str, dict[str, Any]] = {}
    etf_results: list[dict[str, Any]] = []

    for etf_symbol in etf_symbols:
        candidate_path = month_dir / f'{etf_symbol}_{yymm}.md'
        if not candidate_path.exists():
            etf_results.append({'etf_symbol': etf_symbol, 'exists': False, 'reason': 'missing_month_output'})
            continue
        try:
            payload = load_json(candidate_path)
        except Exception:
            etf_results.append({'etf_symbol': etf_symbol, 'exists': False, 'reason': 'non_json_month_output'})
            continue

        rows = payload.get('rows', []) if isinstance(payload, dict) else []
        added = 0
        for row in rows:
            symbol = str(row.get('constituent_symbol') or '').strip().upper()
            if not symbol:
                continue
            item = reverse_map.setdefault(symbol, {
                'symbol': symbol,
                'target_month': args.target_month,
                'held_by': [],
            })
            item['held_by'].append({
                'etf_symbol': etf_symbol,
                'weight_percent': safe_weight(row.get('weight_percent')),
                'constituent_name': row.get('constituent_name'),
                'source_path': str(candidate_path),
            })
            added += 1
        etf_results.append({'etf_symbol': etf_symbol, 'exists': True, 'row_count': len(rows), 'mapped_rows': added, 'path': str(candidate_path)})

    for payload in reverse_map.values():
        payload['held_by'] = sorted(
            payload['held_by'],
            key=lambda item: (
                item.get('weight_percent') is None,
                -(item.get('weight_percent') or 0.0),
                str(item.get('etf_symbol') or ''),
            ),
        )
        payload['etf_count'] = len(payload['held_by'])

    output = {
        'kind': 'etf_holdings_reverse_symbol_map',
        'target_month': args.target_month,
        'month_dir': str(month_dir),
        'symbol_count': len(reverse_map),
        'symbols': dict(sorted(reverse_map.items())),
        'etf_results': etf_results,
    }

    out_path = month_dir / f'_reverse_symbol_map_{yymm}.json'
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'target_month': args.target_month, 'symbol_count': len(reverse_map), 'output_path': str(out_path)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
