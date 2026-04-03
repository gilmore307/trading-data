from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from src.data.common.month_meta_utils import load_effective_meta


def iter_rows(path: str | Path) -> Iterator[dict[str, Any]]:
    jsonl_path = Path(path)
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
