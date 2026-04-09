from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.data.common.storage_paths import market_tape_options_snapshots_root

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = market_tape_options_snapshots_root()
META_NAME = "options_snapshots.meta.json"
DATASET_NAME = "options_snapshots.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def extract_meta(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    sample = rows[0]
    meta = {
        "source": sample.get("source"),
        "dataset": sample.get("dataset"),
        "underlying_symbol": sample.get("underlying_symbol"),
        "storage_format": "options_snapshot_v2_row_meta_split",
        "row_fields": ["option_symbol", "ts", "timestamp", "snapshot"],
    }
    return meta


def compact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append({
            "option_symbol": row.get("option_symbol"),
            "ts": row.get("ts"),
            "timestamp": row.get("timestamp"),
            "snapshot": row.get("snapshot"),
        })
    return out


def convert_file(path: Path, *, apply: bool) -> dict[str, Any]:
    rows = load_jsonl(path)
    before_bytes = path.stat().st_size
    meta_path = path.with_name(META_NAME)

    already_compact = bool(rows) and all(sorted(r.keys()) == ["option_symbol", "snapshot", "timestamp", "ts"] for r in rows)
    existing_meta = meta_path.exists()

    if not rows:
        return {
            "path": str(path.relative_to(ROOT)),
            "changed": False,
            "reason": "empty_file",
            "bytes_before": before_bytes,
            "bytes_after": before_bytes,
            "bytes_saved": 0,
        }

    if already_compact and existing_meta:
        return {
            "path": str(path.relative_to(ROOT)),
            "changed": False,
            "reason": "already_normalized",
            "bytes_before": before_bytes,
            "bytes_after": before_bytes,
            "bytes_saved": 0,
        }

    meta = extract_meta(rows)
    compact = compact_rows(rows)
    compact_bytes = sum(len(json.dumps(r, ensure_ascii=False)) + 1 for r in compact)
    meta_bytes = len(json.dumps(meta, ensure_ascii=False, indent=2)) + 1
    after_bytes = compact_bytes + meta_bytes

    if apply:
        with path.open("w", encoding="utf-8") as f:
            for row in compact:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        after_bytes = path.stat().st_size + meta_path.stat().st_size

    return {
        "path": str(path.relative_to(ROOT)),
        "meta_path": str(meta_path.relative_to(ROOT)),
        "changed": True,
        "reason": "normalized_to_row_meta_split",
        "row_count": len(rows),
        "bytes_before": before_bytes,
        "bytes_after": after_bytes,
        "bytes_saved": max(before_bytes - after_bytes, 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize options_snapshots storage into row-data + month-meta layout.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--only", nargs="*", default=None, help="relative options_snapshots.jsonl paths under trading-storage/2_market_tape/2_rolling/5_options_snapshots/")
    args = parser.parse_args()

    if args.only:
        paths = [DATA_ROOT / rel for rel in args.only]
    else:
        paths = sorted(DATA_ROOT.rglob(DATASET_NAME))

    reports = []
    totals = {
        "files": 0,
        "changed_files": 0,
        "bytes_before": 0,
        "bytes_after": 0,
        "bytes_saved": 0,
    }

    for path in paths:
        if path.name != DATASET_NAME or not path.exists():
            continue
        report = convert_file(path, apply=args.apply)
        reports.append(report)
        totals["files"] += 1
        totals["changed_files"] += 1 if report["changed"] else 0
        totals["bytes_before"] += int(report["bytes_before"])
        totals["bytes_after"] += int(report["bytes_after"])
        totals["bytes_saved"] += int(report["bytes_saved"])

    print(json.dumps({"apply": args.apply, "totals": totals, "reports": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
