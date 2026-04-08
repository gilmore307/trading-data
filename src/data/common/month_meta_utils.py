from __future__ import annotations

from pathlib import Path
from typing import Any


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
    elif dataset_name == 'quotes_1min.jsonl':
        inferred.update({'dataset': 'quotes_1min'})
    elif dataset_name == 'trades_1min.jsonl':
        inferred.update({'dataset': 'trades_1min'})
    elif dataset_name == 'options_snapshots.jsonl':
        inferred.update({'dataset': 'options_snapshot', 'underlying_symbol': symbol})

    if '-' in symbol:
        inferred.setdefault('asset_class', 'crypto')
    else:
        inferred.setdefault('asset_class', 'stocks')
    return inferred


def load_effective_meta(jsonl_path: Path) -> dict[str, Any]:
    return infer_from_path(jsonl_path)
