from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.data.common.storage_paths import market_tape_root

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = market_tape_root() / '1_long_retention'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def minify_meta(month_dir: Path, *, apply: bool) -> dict[str, Any]:
    meta_path = month_dir / '_meta.json'
    if not meta_path.exists():
        return {
            'path': str(month_dir.relative_to(ROOT)),
            'changed': False,
            'reason': 'no_dir_meta',
        }

    old = load_json(meta_path)
    old_bytes = meta_path.stat().st_size
    datasets = old.get('datasets') or {}

    new_meta: dict[str, Any] = {}
    if 'source' in old:
        new_meta['source'] = old['source']

    # find shared values across dataset entries
    shared_candidates: dict[str, Any] | None = None
    normalized: dict[str, dict[str, Any]] = {}

    for dataset_key, payload in datasets.items():
        ds = dict(payload)
        if 'meta' in ds and isinstance(ds['meta'], dict):
            flat = dict(ds['meta'])
        else:
            flat = ds
        flat.pop('row_fields', None)
        flat.pop('storage_format', None)
        flat.pop('symbol', None)
        flat.pop('underlying_symbol', None)
        normalized[dataset_key] = flat
        if shared_candidates is None:
            shared_candidates = dict(flat)
        else:
            for k in list(shared_candidates.keys()):
                if flat.get(k) != shared_candidates[k]:
                    shared_candidates.pop(k, None)

    shared = shared_candidates or {}
    for k in ['asset_class', 'feed_scope']:
        if k in shared:
            new_meta[k] = shared[k]

    compact_datasets: dict[str, dict[str, Any]] = {}
    for dataset_key, flat in normalized.items():
        ds_compact = {k: v for k, v in flat.items() if new_meta.get(k) != v}
        # dataset value is needed unless it can be trivially inferred and still stay stable for readers
        compact_datasets[dataset_key] = ds_compact

    new_meta['datasets'] = compact_datasets
    payload = json.dumps(new_meta, ensure_ascii=False, separators=(',', ':')) + '\n'
    new_bytes = len(payload.encode('utf-8'))

    if apply:
        meta_path.write_text(payload, encoding='utf-8')
        new_bytes = meta_path.stat().st_size

    return {
        'path': str(month_dir.relative_to(ROOT)),
        'changed': new_bytes != old_bytes,
        'bytes_before': old_bytes,
        'bytes_after': new_bytes,
        'bytes_saved': max(old_bytes - new_bytes, 0),
        'old': old,
        'new': new_meta,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Minify directory-level _meta.json by lifting shared fields and removing path-derivable fields')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--only', nargs='*', default=None, help='relative month dirs under trading-storage/2_market_tape/1_long_retention/')
    args = parser.parse_args()

    if args.only:
        dirs = [DATA_ROOT / rel for rel in args.only]
    else:
        dirs = sorted([p for p in DATA_ROOT.glob('*/*') if p.is_dir()])

    reports = []
    totals = {'dirs': 0, 'changed_dirs': 0, 'bytes_before': 0, 'bytes_after': 0, 'bytes_saved': 0}
    for d in dirs:
        report = minify_meta(d, apply=args.apply)
        reports.append(report)
        totals['dirs'] += 1
        totals['changed_dirs'] += 1 if report.get('changed') else 0
        totals['bytes_before'] += int(report.get('bytes_before', 0) or 0)
        totals['bytes_after'] += int(report.get('bytes_after', 0) or 0)
        totals['bytes_saved'] += int(report.get('bytes_saved', 0) or 0)

    print(json.dumps({'apply': args.apply, 'totals': totals, 'reports': reports}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
