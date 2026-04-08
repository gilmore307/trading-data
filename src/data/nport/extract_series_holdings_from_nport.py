from __future__ import annotations

import argparse
import csv
import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterator

import requests

ROOT = Path(__file__).resolve().parents[3]
DISCOVERY_PATH = ROOT / 'context' / 'etf_holdings' / '_aux' / 'discovery' / 'nport_discovery.json'
MAPPING_PATH = ROOT / 'context' / 'etf_holdings' / '_aux' / 'mapping' / 'sec_series_mapping_candidates_2603.json'
OUT_DIR = ROOT / 'context' / 'etf_holdings'
KEEP_ZIP_DIR = ROOT / 'context' / 'etf_holdings' / '_aux' / 'nport_data' / 'packages'
USER_AGENT = 'Mozilla/5.0 trading-data-research local'


def yy_mm_from_target_month(target_month: str | None) -> str:
    if not target_month:
        return 'unknown'
    year, month = target_month.split('-', 1)
    return f"{year[2:]}{month}"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def latest_package_url() -> str:
    discovery = load_json(DISCOVERY_PATH)
    latest = discovery.get('latest')
    if not latest:
        raise ValueError('no latest discovered package available')
    return latest['url']


def stream_download(url: str, target: Path) -> Path:
    with requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=120, stream=True) as resp:
        resp.raise_for_status()
        with target.open('wb') as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    return target


def iter_tsv_from_zip(zip_path: Path, member: str) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(member) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8', newline=''), delimiter='\t')
            for row in reader:
                yield row


def choose_series(mapping: dict[str, Any], etf_symbol: str) -> dict[str, Any]:
    matches = mapping.get('matches', {}).get(etf_symbol, [])
    if not matches:
        raise ValueError(f'no candidate SEC series mapping for {etf_symbol}')
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser(description='Extract ETF-specific holdings candidates from latest N-PORT package using a candidate series mapping.')
    parser.add_argument('--etf-symbol', required=True)
    parser.add_argument('--mapping', type=Path, default=MAPPING_PATH)
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--target-month', default='2026-03')
    parser.add_argument('--keep-zip', action='store_true')
    args = parser.parse_args()

    mapping = load_json(args.mapping)
    series = choose_series(mapping, args.etf_symbol)
    series_id = series.get('SERIES_ID') or None
    series_lei = series.get('SERIES_LEI') or None
    if not series_id and not series_lei:
        raise ValueError(f'candidate mapping for {args.etf_symbol} has neither SERIES_ID nor SERIES_LEI')

    url = latest_package_url()
    with tempfile.TemporaryDirectory(prefix='nport_') as tmpdir:
        zip_path = Path(tmpdir) / Path(url).name
        stream_download(url, zip_path)

        relevant_accessions: set[str] = set()
        for row in iter_tsv_from_zip(zip_path, 'FUND_REPORTED_INFO.tsv'):
            row_series_id = row.get('SERIES_ID') or None
            row_series_lei = row.get('SERIES_LEI') or None
            matched = False
            if series_id and row_series_id == series_id:
                matched = True
            elif series_lei and row_series_lei == series_lei:
                matched = True
            if matched and row.get('ACCESSION_NUMBER'):
                relevant_accessions.add(row['ACCESSION_NUMBER'])

        if not relevant_accessions:
            raise ValueError(f'no accessions found for series_id={series_id} series_lei={series_lei}')

        holdings_by_id: dict[str, dict[str, Any]] = {}
        for row in iter_tsv_from_zip(zip_path, 'FUND_REPORTED_HOLDING.tsv'):
            accession_number = row.get('ACCESSION_NUMBER')
            if accession_number not in relevant_accessions:
                continue
            holding_id = row.get('HOLDING_ID')
            if not holding_id:
                continue
            holdings_by_id[holding_id] = {
                'etf_symbol': args.etf_symbol,
                'as_of_date': None,
                'constituent_symbol': row.get('ISSUER_CUSIP'),
                'constituent_name': row.get('ISSUER_NAME') or row.get('ISSUER_TITLE'),
                'weight_percent': row.get('PERCENTAGE'),
                'holding_id': holding_id,
                'accession_number': accession_number,
                'series_id': series_id,
                'series_lei': series_lei,
            }

        for row in iter_tsv_from_zip(zip_path, 'IDENTIFIERS.tsv'):
            holding_id = row.get('HOLDING_ID')
            if not holding_id or holding_id not in holdings_by_id:
                continue
            ticker = row.get('IDENTIFIER_TICKER')
            if ticker:
                holdings_by_id[holding_id]['constituent_symbol'] = ticker

        normalized = list(holdings_by_id.values())

        yymm = yy_mm_from_target_month(args.target_month)
        default_dir = OUT_DIR / yymm
        default_dir.mkdir(parents=True, exist_ok=True)
        out_path = args.out or (default_dir / f'{args.etf_symbol}_{yymm}.md')
        out_path.write_text(json.dumps({
            'etf_symbol': args.etf_symbol,
            'target_month': args.target_month,
            'series_candidate': series,
            'rows': normalized,
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        print(json.dumps({
            'etf_symbol': args.etf_symbol,
            'series_id': series_id,
            'series_lei': series_lei,
            'accession_count': len(relevant_accessions),
            'row_count': len(normalized),
            'output': str(out_path),
            'streaming_mode': True,
        }, ensure_ascii=False, indent=2))

        if args.keep_zip:
            keep_path = KEEP_ZIP_DIR / Path(url).stem / Path(url).name
            keep_path.parent.mkdir(parents=True, exist_ok=True)
            keep_path.write_bytes(zip_path.read_bytes())


if __name__ == '__main__':
    main()
