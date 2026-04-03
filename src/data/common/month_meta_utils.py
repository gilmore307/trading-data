from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def infer_from_path(jsonl_path: Path) -> dict[str, Any]:
    month_dir = jsonl_path.parent
    symbol_dir = month_dir.parent
    symbol = symbol_dir.name
    dataset_name = jsonl_path.name

    inferred: dict[str, Any] = {
        'symbol': symbol,
        'month': month_dir.name,
    }

    if dataset_name == 'bars_1min.jsonl':
        inferred.update({'dataset': 'bars', 'timeframe': '1Min'})
    elif dataset_name == 'quotes.jsonl':
        inferred.update({'dataset': 'quotes'})
    elif dataset_name == 'trades.jsonl':
        inferred.update({'dataset': 'trades'})
    elif dataset_name == 'options_snapshots.jsonl':
        inferred.update({'dataset': 'options_snapshot', 'underlying_symbol': symbol})

    if '-' in symbol:
        inferred.setdefault('asset_class', 'crypto')
    else:
        inferred.setdefault('asset_class', 'stocks')
    return inferred


def load_effective_meta(jsonl_path: Path) -> dict[str, Any]:
    inferred = infer_from_path(jsonl_path)
    meta: dict[str, Any] = {}

    dir_meta_path = jsonl_path.parent / '_meta.json'
    dataset_key = DATASET_KEY_BY_FILENAME.get(jsonl_path.name)
    if dir_meta_path.exists() and dataset_key:
        dir_meta = json.loads(dir_meta_path.read_text(encoding='utf-8'))
        meta.update({k: v for k, v in dir_meta.items() if k != 'datasets'})
        ds = (dir_meta.get('datasets') or {}).get(dataset_key) or {}
        meta.update(ds)
        final = dict(inferred)
        final.update(meta)
        return final

    legacy_name = LEGACY_META_BY_FILENAME.get(jsonl_path.name)
    if legacy_name:
        legacy_path = jsonl_path.with_name(legacy_name)
        if legacy_path.exists():
            legacy = json.loads(legacy_path.read_text(encoding='utf-8'))
            legacy.pop('storage_format', None)
            legacy.pop('row_fields', None)
            final = dict(inferred)
            final.update(legacy)
            return final

    return inferred


def build_dataset_meta_compact(dataset_key: str, sample: dict[str, Any]) -> dict[str, Any]:
    if dataset_key == 'bars_1min':
        return {
            'dataset': 'bars',
            'symbol': sample.get('symbol'),
            'asset_class': sample.get('asset_class'),
            'feed_scope': sample.get('feed_scope'),
            'timeframe': sample.get('timeframe'),
        }
    if dataset_key == 'quotes':
        return {
            'dataset': 'quotes',
            'symbol': sample.get('symbol'),
            'asset_class': sample.get('asset_class'),
            'feed_scope': sample.get('feed_scope'),
        }
    if dataset_key == 'trades':
        return {
            'dataset': 'trades',
            'symbol': sample.get('symbol'),
            'asset_class': sample.get('asset_class'),
            'feed_scope': sample.get('feed_scope'),
        }
    if dataset_key == 'options_snapshots':
        return {
            'dataset': 'options_snapshot',
            'underlying_symbol': sample.get('underlying_symbol'),
            'asset_class': sample.get('asset_class'),
        }
    raise ValueError(f'unsupported dataset_key: {dataset_key}')


def write_month_dir_meta(month_dir: Path, dataset_key: str, sample: dict[str, Any]) -> None:
    month_dir.mkdir(parents=True, exist_ok=True)
    meta_path = month_dir / '_meta.json'
    payload: dict[str, Any] = {'datasets': {}}
    if meta_path.exists():
        payload = json.loads(meta_path.read_text(encoding='utf-8'))
        if not isinstance(payload.get('datasets'), dict):
            payload['datasets'] = {}
    if sample.get('source') is not None:
        payload['source'] = sample.get('source')

    payload['datasets'][dataset_key] = build_dataset_meta_compact(dataset_key, sample)
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
