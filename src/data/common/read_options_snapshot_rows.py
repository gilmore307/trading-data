from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

META_NAME = "options_snapshots.meta.json"


def iter_options_snapshot_rows(path: str | Path) -> Iterator[dict[str, Any]]:
    jsonl_path = Path(path)
    meta_path = jsonl_path.with_name(META_NAME)
    meta: dict[str, Any] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if meta:
                merged = dict(meta)
                merged.pop("storage_format", None)
                merged.pop("row_fields", None)
                merged.update(row)
                yield merged
            else:
                yield row
