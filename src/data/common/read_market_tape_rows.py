from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from src.data.common.month_meta_utils import load_effective_meta


def _iter_jsonl(jsonl_path: Path) -> Iterator[dict[str, Any]]:
    meta = load_effective_meta(jsonl_path)
    with jsonl_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            merged = dict(meta)
            merged.update(row)
            yield merged


def iter_rows(path: str | Path) -> Iterator[dict[str, Any]]:
    base_path = Path(path)

    if base_path.is_file():
        yield from _iter_jsonl(base_path)
        return

    if base_path.is_dir():
        manifest_path = base_path / '_manifest.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            for part in manifest.get('parts', []):
                part_path = Path(part['path'])
                if part_path.exists():
                    yield from _iter_jsonl(part_path)
            return

        for part_path in sorted(base_path.glob('part-*.jsonl')):
            yield from _iter_jsonl(part_path)
        return

    raise FileNotFoundError(base_path)
