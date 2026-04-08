from __future__ import annotations

import argparse
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[3]
DISCOVERY_PATH = ROOT / 'context' / 'etf_holdings' / '_aux' / 'discovery' / 'nport_discovery.json'
OUT_DIR = ROOT / 'context' / 'etf_holdings' / '_aux' / 'nport_data' / 'packages'


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace('+00:00', 'Z')


def load_discovery(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> None:
    parser = argparse.ArgumentParser(description='Download SEC N-PORT package metadata and selected small files from the latest discovered dataset zip.')
    parser.add_argument('--discovery', type=Path, default=DISCOVERY_PATH)
    parser.add_argument('--url', default=None)
    parser.add_argument('--out-dir', type=Path, default=OUT_DIR)
    parser.add_argument('--max-bytes', type=int, default=32 * 1024 * 1024)
    args = parser.parse_args()

    if args.url:
        url = args.url
        package_name = Path(url).name
    else:
        discovery = load_discovery(args.discovery)
        latest = discovery.get('latest')
        if not latest:
            raise ValueError('no latest N-PORT dataset found in discovery file')
        url = latest['url']
        package_name = latest['name']

    headers = {'User-Agent': 'Mozilla/5.0 trading-data-research local'}
    resp = requests.get(url, headers=headers, timeout=120)
    resp.raise_for_status()
    if len(resp.content) > args.max_bytes:
        raise ValueError(f'zip too large for metadata-only helper: {len(resp.content)} bytes > max {args.max_bytes}')

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    package_dir = args.out_dir / package_name.removesuffix('.zip')
    package_dir.mkdir(parents=True, exist_ok=True)

    selected = ['nport_metadata.json', 'nport_readme.htm']
    written = []
    for name in selected:
        if name not in names:
            continue
        target = package_dir / name
        target.write_bytes(zf.read(name))
        written.append(str(target))

    manifest = {
        'downloaded_at': now_iso(),
        'url': url,
        'package_name': package_name,
        'zip_size_bytes': len(resp.content),
        'members': names,
        'written': written,
    }
    (package_dir / '_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
