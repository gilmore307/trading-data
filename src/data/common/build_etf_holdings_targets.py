from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
ETF_CONTEXT_UNIVERSE = ROOT / 'config' / 'etf_context_universe.json'
OUT_PATH = ROOT / 'config' / 'etf_holdings_target_universe.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def rows_to_symbols(rows: list[dict[str, Any]]) -> list[str]:
    out = []
    seen = set()
    for row in rows:
        symbol = row.get('symbol')
        if symbol and symbol not in seen:
            seen.add(symbol)
            out.append(symbol)
    return out


def pick_priority(rows: list[dict[str, Any]], allowed_priorities: set[str]) -> list[str]:
    out = []
    seen = set()
    for row in rows:
        symbol = row.get('symbol')
        priority = row.get('priority')
        if symbol and priority in allowed_priorities and symbol not in seen:
            seen.add(symbol)
            out.append(symbol)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description='Build actionable ETF holdings target tiers from the broader ETF context universe config.')
    parser.add_argument('--input', type=Path, default=ETF_CONTEXT_UNIVERSE)
    parser.add_argument('--out', type=Path, default=OUT_PATH)
    args = parser.parse_args()

    payload = load_json(args.input)
    categories = payload['categories']

    out = {
        'version': 1,
        'last_updated': payload.get('last_updated'),
        'purpose': 'Priority ETF target universe for holdings extraction/refresh workflows.',
        'notes': [
            'This file is the actionable ETF holdings target list derived from the broader ETF context universe.',
            'trading-data should prioritize durable holdings coverage for this list before expanding wider.',
            'trading-model may still score/prune final usefulness downstream.',
        ],
        'tiers': {
            'tier_1_core_broad_market': rows_to_symbols(categories['core_broad_market']),
            'tier_2_core_sector': rows_to_symbols(categories['core_sector']),
            'tier_3_priority_macro_proxy': pick_priority(categories['macro_commodity_crypto_proxy'], {'high'}),
            'tier_4_priority_industry_thematic': (
                pick_priority(categories['industry_subindustry'], {'high'})
                + pick_priority(categories['resource_transition'], {'high'})
                + pick_priority(categories['thematic_high_attention'], {'high'})
            ),
        },
    }

    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
