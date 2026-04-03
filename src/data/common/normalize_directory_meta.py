from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT / 'data'
DIR_META_NAME = '_meta.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def build_dir_meta(month_dir: Path) -> dict[str, Any] | None:
    meta_files = sorted(month_dir.glob('*.meta.json'))
    if not meta_files:
        return None

    datasets: dict[str, Any] = {}
    shared_source = None

    for meta_path in meta_files:
        obj = load_json(meta_path)
        dataset_key = meta_path.name.replace('.meta.json', '')
        row_fields = obj.pop('row_fields', None)
        storage_format = obj.pop('storage_format', None)

        if shared_source is None and 'source' in obj:
            shared_source = obj['source']
        if 'source' in obj and shared_source == obj['source']:
            obj.pop('source', None)

        datasets[dataset_key] = {
            'row_fields': row_fields,
            'storage_format': storage_format,
            'meta': obj,
        }

    dir_meta: dict[str, Any] = {
        'storage_format': 'month_dir_meta_v1',
        'datasets': datasets,
    }
    if shared_source is not None:
        dir_meta['source'] = shared_source

    return dir_meta


def convert_dir(month_dir: Path, *, apply: bool) -> dict[str, Any]:
    dir_meta = build_dir_meta(month_dir)
    if dir_meta is None:
        return {
            'path': str(month_dir.relative_to(ROOT)),
            'changed': False,
            'reason': 'no_dataset_meta_files',
        }

    dir_meta_path = month_dir / DIR_META_NAME
    meta_files = sorted(month_dir.glob('*.meta.json'))
    before_bytes = sum(p.stat().st_size for p in meta_files)
    after_payload = json.dumps(dir_meta, ensure_ascii=False, indent=2) + '\n'
    after_bytes = len(after_payload.encode('utf-8'))

    changed = True
    if apply:
        dir_meta_path.write_text(after_payload, encoding='utf-8')
        for p in meta_files:
            p.unlink()
        after_bytes = dir_meta_path.stat().st_size

    return {
        'path': str(month_dir.relative_to(ROOT)),
        'changed': changed,
        'meta_files_before': [p.name for p in meta_files],
        'meta_file_after': str(dir_meta_path.relative_to(ROOT)),
        'bytes_before': before_bytes,
        'bytes_after': after_bytes,
        'bytes_saved': max(before_bytes - after_bytes, 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Collapse per-dataset month meta files into one shared directory _meta.json')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--only', nargs='*', default=None, help='relative month directories under data/')
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
