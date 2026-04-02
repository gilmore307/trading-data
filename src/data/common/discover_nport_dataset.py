from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[3]
SEC_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets"
OUT_PATH = ROOT / "context" / "etf_holdings" / "_nport_discovery.json"
ZIP_RE = re.compile(r'/files/dera/data/form-n-port-data-sets/(?P<name>(?P<year>\d{4})q(?P<quarter>[1-4])_nport\.zip)')


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace('+00:00', 'Z')


def quarter_sort_key(item: dict[str, Any]) -> tuple[int, int]:
    return (int(item['year']), int(item['quarter']))


def main() -> None:
    parser = argparse.ArgumentParser(description='Discover available SEC Form N-PORT quarterly dataset packages.')
    parser.add_argument('--out', type=Path, default=OUT_PATH)
    parser.add_argument('--page-url', default=SEC_PAGE)
    args = parser.parse_args()

    headers = {
        'User-Agent': 'Mozilla/5.0 trading-data-research local',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    resp = requests.get(args.page_url, headers=headers, timeout=30)
    resp.raise_for_status()
    html = resp.text

    seen = {}
    for m in ZIP_RE.finditer(html):
        name = m.group('name')
        rel = m.group(0)
        seen[name] = {
            'name': name,
            'year': int(m.group('year')),
            'quarter': int(m.group('quarter')),
            'relative_url': rel,
            'url': f'https://www.sec.gov{rel}',
        }

    datasets = sorted(seen.values(), key=quarter_sort_key)
    latest = datasets[-1] if datasets else None
    payload = {
        'checked_at': now_iso(),
        'page_url': args.page_url,
        'dataset_count': len(datasets),
        'latest': latest,
        'datasets': datasets,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
