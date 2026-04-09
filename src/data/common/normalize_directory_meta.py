from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.data.common.storage_paths import market_tape_root

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = market_tape_root() / '2_rolling'
DIR_META_NAME = '_meta.json'

DATASET_META_FILENAMES = {
    'bars_1min.meta.json': 'bars_1min',
    'quotes.meta.json': 'quotes',
    'trades.meta.json': 'trades',
    'options_snapshots.meta.json': 'options_snapshots',
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def build_compact_dir_meta(month_dir: Path) -> tuple[dict[str, Any], list[Path]] | tuple[None, list[Path]]:
    meta_files = sorted([p for p in month_dir.glob('*.meta.json') if p.name in DATASET_META_FILENAMES])
    if not meta_files:
        return None, []

    dataset_payloads: dict[str, dict[str, Any]] = {}
    shared_candidates: dict[str, Any] | None = None

    for meta_path in meta_files:
        obj = load_json(meta_path)
        dataset_key = DATASET_META_FILENAMES[meta_path.name]
        obj.pop('row_fields', None)
        obj.pop('storage_format', None)
        dataset_payloads[dataset_key] = obj
        if shared_candidates is None:
            shared_candidates = dict(obj)
        else:
            for k in list(shared_candidates.keys()):
                if obj.get(k) != shared_candidates[k]:
                    shared_candidates.pop(k, None)

    shared = shared_candidates or {}
    # only keep truly useful shared keys at top level
    allowed_shared = {'source', 'symbol', 'asset_class', 'feed_scope', 'underlying_symbol'}
    shared = {k: v for k, v in shared.items() if k in allowed_shared}

    datasets: dict[str, dict[str, Any]] = {}
    for dataset_key, obj in dataset_payloads.items():
        specific = {k: v for k, v in obj.items() if shared.get(k) != v}
        datasets[dataset_key] = specific

    dir_meta: dict[str, Any] = {}
    dir_meta.update(shared)
    dir_meta['datasets'] = datasets
    return dir_meta, meta_files


def convert_dir(month_dir: Path, *, apply: bool) -> dict[str, Any]:
    dir_meta, meta_files = build_compact_dir_meta(month_dir)
    if dir_meta is None:
        return {
            'path': str(month_dir.relative_to(ROOT)),
            'changed': False,
            'reason': 'no_dataset_meta_files',
        }

    dir_meta_path = month_dir / DIR_META_NAME
    before_bytes = sum(p.stat().st_size for p in meta_files)
    after_payload = json.dumps(dir_meta, ensure_ascii=False, separators=(',', ':')) + '\n'
    after_bytes = len(after_payload.encode('utf-8'))

    if apply:
        dir_meta_path.write_text(after_payload, encoding='utf-8')
        for p in meta_files:
            p.unlink()
        after_bytes = dir_meta_path.stat().st_size

    return {
        'path': str(month_dir.relative_to(ROOT)),
        'changed': True,
        'meta_files_before': [p.name for p in meta_files],
        'meta_file_after': str(dir_meta_path.relative_to(ROOT)),
        'bytes_before': before_bytes,
        'bytes_after': after_bytes,
        'bytes_saved': max(before_bytes - after_bytes, 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Collapse per-dataset month meta files into one compact shared directory _meta.json')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--only', nargs='*', default=None, help='relative month directories under trading-storage/2_market_tape/2_rolling/')
    args = parser.parse_args()

    if args.only:
        dirs = [DATA_ROOT / rel for rel in args.only]
    else:
        dirs = sorted([p for p in DATA_ROOT.glob('*/*') if p.is_dir()])

    reports = []
    totals = {'dirs': 0, 'changed_dirs': 0, 'bytes_before': 0, 'bytes_after': 0, 'bytes_saved': 0}
    for d in dirs:
        report = convert_dir(d, apply=args.apply)
        reports.append(report)
        totals['dirs'] += 1
        totals['changed_dirs'] += 1 if report.get('changed') else 0
        totals['bytes_before'] += int(report.get('bytes_before', 0) or 0)
        totals['bytes_after'] += int(report.get('bytes_after', 0) or 0)
        totals['bytes_saved'] += int(report.get('bytes_saved', 0) or 0)

    print(json.dumps({'apply': args.apply, 'totals': totals, 'reports': reports}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
