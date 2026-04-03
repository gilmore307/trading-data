from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

DATASET_KEY_BY_FILENAME = {
    'bars_1min.jsonl': 'bars_1min',
    'quotes.jsonl': 'quotes',
    'trades.jsonl': 'trades',
    'options_snapshots.jsonl': 'options_snapshots',
}

LEGACY_META_BY_FILENAME = {
    'bars_1min.jsonl': 'bars_1min.meta.json',
    'quotes.jsonl': 'quotes.meta.json',
    'trades.jsonl': 'trades.meta.json',
    'options_snapshots.jsonl': 'options_snapshots.meta.json',
}


def infer_fallback_meta(jsonl_path: Path) -> dict[str, Any]:
    month_dir = jsonl_path.parent
    symbol_dir = month_dir.parent
    symbol = symbol_dir.name
    dataset_name = jsonl_path.name
    inferred: dict[str, Any] = {}

    if dataset_name == 'bars_1min.jsonl':
        inferred = {'dataset': 'bars', 'timeframe': '1Min'}
    elif dataset_name == 'quotes.jsonl':
        inferred = {'dataset': 'quotes'}
    elif dataset_name == 'trades.jsonl':
        inferred = {'dataset': 'trades'}
    elif dataset_name == 'options_snapshots.jsonl':
        inferred = {'dataset': 'options_snapshot', 'underlying_symbol': symbol}

    return inferred


def load_effective_meta(jsonl_path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {}

    dir_meta_path = jsonl_path.parent / '_meta.json'
    dataset_key = DATASET_KEY_BY_FILENAME.get(jsonl_path.name)
    if dir_meta_path.exists() and dataset_key:
        dir_meta = json.loads(dir_meta_path.read_text(encoding='utf-8'))
        meta.update({k: v for k, v in dir_meta.items() if k != 'datasets'})
        ds = (dir_meta.get('datasets') or {}).get(dataset_key) or {}
        meta.update(ds)
        meta.update(infer_fallback_meta(jsonl_path))
        return meta

    legacy_name = LEGACY_META_BY_FILENAME.get(jsonl_path.name)
    if legacy_name:
        legacy_path = jsonl_path.with_name(legacy_name)
        if legacy_path.exists():
            legacy = json.loads(legacy_path.read_text(encoding='utf-8'))
            meta.update(legacy)
            meta.pop('storage_format', None)
            meta.pop('row_fields', None)
            meta.update(infer_fallback_meta(jsonl_path))
            return meta

    meta.update(infer_fallback_meta(jsonl_path))
    return meta


def iter_rows(path: str | Path) -> Iterator[dict[str, Any]]:
    jsonl_path = Path(path)
    meta = load_effective_meta(jsonl_path)

    with jsonl_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if meta:
                merged = dict(meta)
                merged.update(row)
                yield merged
            else:
                yield row
