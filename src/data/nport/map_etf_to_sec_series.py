from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DISCOVERY_PATH = ROOT / 'context' / 'etf_holdings' / '_aux' / 'discovery' / 'nport_discovery.json'
CANDIDATES_PATH = ROOT / 'config' / 'etf_sec_series_candidates.json'
OUT_PATH = ROOT / 'context' / 'etf_holdings' / '_aux' / 'mapping' / 'sec_series_mapping_candidates_2603.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def latest_package_dir() -> Path:
    discovery = load_json(DISCOVERY_PATH)
    latest = discovery.get('latest')
    if not latest:
        raise ValueError('no latest discovered package available')
    return context_etf_aux_root() / 'nport_data' / 'packages' / latest['name'].removesuffix('.zip')


def read_fund_rows(package_dir: Path) -> list[dict[str, str]]:
    manifest = load_json(package_dir / '_manifest.json')
    package_url = manifest['url']

    import requests
    resp = requests.get(package_url, headers={'User-Agent': 'Mozilla/5.0 trading-data-research local'}, timeout=120)
    resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    with zf.open('FUND_REPORTED_INFO.tsv') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8', newline=''), delimiter='\t')
        return list(reader)


def match_rows(rows: list[dict[str, str]], patterns: list[str]) -> list[dict[str, str]]:
    hits = []
    up_patterns = [p.upper() for p in patterns]
    for row in rows:
        hay = ' | '.join(str(v or '') for v in row.values()).upper()
        if any(p in hay for p in up_patterns):
            hits.append(row)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description='Build candidate ETF -> SEC series mapping matches from FUND_REPORTED_INFO.tsv.')
    parser.add_argument('--candidates', type=Path, default=CANDIDATES_PATH)
    parser.add_argument('--out', type=Path, default=OUT_PATH)
    args = parser.parse_args()

    package_dir = latest_package_dir()
    rows = read_fund_rows(package_dir)
    candidates = load_json(args.candidates).get('etfs', {})

    out = {
        'package_dir': str(package_dir),
        'matches': {},
    }
    for etf_symbol, patterns in candidates.items():
        hits = match_rows(rows, patterns)
        out['matches'][etf_symbol] = [
            {
                'SERIES_NAME': row.get('SERIES_NAME'),
                'SERIES_ID': row.get('SERIES_ID'),
                'SERIES_LEI': row.get('SERIES_LEI'),
                'CLASS_ID': row.get('CLASS_ID'),
                'REGISTRANT_NAME': row.get('REGISTRANT_NAME'),
            }
            for row in hits[:20]
        ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
