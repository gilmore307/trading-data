from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
TARGETS_PATH = ROOT / 'config' / 'etf_holdings_target_universe.json'
from src.data.common.storage_paths import context_etf_holdings_root

HOLDINGS_ROOT = context_etf_holdings_root()


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


def main() -> None:
    parser = argparse.ArgumentParser(description='Build a month-level ETF holdings output manifest for downstream consumption.')
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

    month_dir = HOLDINGS_ROOT / yymm
    month_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for symbol in symbols:
        path = month_dir / f'{symbol}_{yymm}.md'
        outputs.append({
            'symbol': symbol,
            'exists': path.exists(),
            'path': str(path),
        })

    manifest = {
        'kind': 'etf_holdings_month_manifest',
        'target_month': args.target_month,
        'month_dir': str(month_dir),
        'outputs': outputs,
    }
    manifest_path = month_dir / f'_manifest_{yymm}.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'manifest_path': str(manifest_path), 'outputs': outputs}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
