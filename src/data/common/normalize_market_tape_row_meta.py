from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.data.common.storage_paths import market_tape_root

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = market_tape_root() / "2_rolling"
MIN_ROWS_FOR_META_SPLIT = 2

DATASET_CONFIGS: dict[str, dict[str, Any]] = {
    "bars_1min.jsonl": {
        "meta_name": "bars_1min.meta.json",
        "storage_format": "bars_1min_v2_row_meta_split",
        "meta_keys": ["source", "asset_class", "feed_scope", "dataset", "symbol", "timeframe"],
        "row_keys": ["ts", "timestamp", "open", "high", "low", "close", "volume", "trade_count", "vwap"],
    },
    "quotes.jsonl": {
        "meta_name": "quotes.meta.json",
        "storage_format": "quotes_v2_row_meta_split",
        "meta_keys": ["source", "asset_class", "feed_scope", "dataset", "symbol"],
        "row_keys": ["ts", "timestamp", "bid_price", "bid_size", "bid_exchange", "ask_price", "ask_size", "ask_exchange", "conditions"],
    },
    "trades.jsonl": {
        "meta_name": "trades.meta.json",
        "storage_format": "trades_v2_row_meta_split",
        "meta_keys": ["source", "asset_class", "feed_scope", "dataset", "symbol"],
        "row_keys": ["ts", "timestamp", "price", "size", "exchange", "conditions", "trade_id", "tape"],
    },
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def is_already_compact(rows: list[dict[str, Any]], row_keys: list[str]) -> bool:
    if not rows:
        return False
    wanted = sorted(row_keys)
    return all(sorted(row.keys()) == wanted for row in rows)


def convert_file(path: Path, cfg: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    rows = load_jsonl(path)
    before_bytes = path.stat().st_size
    meta_path = path.with_name(cfg["meta_name"])

    if not rows:
        return {
            "path": str(path.relative_to(ROOT)),
            "changed": False,
            "reason": "empty_file",
            "bytes_before": before_bytes,
            "bytes_after": before_bytes,
            "bytes_saved": 0,
        }

    if len(rows) < MIN_ROWS_FOR_META_SPLIT:
        return {
            "path": str(path.relative_to(ROOT)),
            "changed": False,
            "reason": "below_meta_split_threshold",
            "bytes_before": before_bytes,
            "bytes_after": before_bytes,
            "bytes_saved": 0,
        }

    if is_already_compact(rows, cfg["row_keys"]) and meta_path.exists():
        return {
            "path": str(path.relative_to(ROOT)),
            "changed": False,
            "reason": "already_normalized",
            "bytes_before": before_bytes,
            "bytes_after": before_bytes + meta_path.stat().st_size,
            "bytes_saved": 0,
        }

    meta = {k: rows[0].get(k) for k in cfg["meta_keys"]}
    meta["storage_format"] = cfg["storage_format"]
    meta["row_fields"] = cfg["row_keys"]

    compact_rows = [{k: row.get(k) for k in cfg["row_keys"]} for row in rows]
    compact_bytes = sum(len(json.dumps(r, ensure_ascii=False)) + 1 for r in compact_rows)
    meta_bytes = len(json.dumps(meta, ensure_ascii=False, indent=2)) + 1
    after_bytes = compact_bytes + meta_bytes

    if after_bytes >= before_bytes:
        return {
            "path": str(path.relative_to(ROOT)),
            "changed": False,
            "reason": "no_size_gain",
            "bytes_before": before_bytes,
            "bytes_after": after_bytes,
            "bytes_saved": 0,
        }

    if apply:
        with path.open("w", encoding="utf-8") as f:
            for row in compact_rows:
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
        "bytes_saved": before_bytes - after_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize market-tape JSONL datasets into row-data + month-meta layout when profitable.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--only", nargs="*", default=None, help="relative dataset paths under trading-storage/2_market_tape/1_data/")
    args = parser.parse_args()

    if args.only:
        paths = [DATA_ROOT / rel for rel in args.only]
    else:
        paths = sorted(p for p in DATA_ROOT.rglob("*.jsonl") if p.name in DATASET_CONFIGS)

    reports = []
    totals = {
        "files": 0,
        "changed_files": 0,
        "bytes_before": 0,
        "bytes_after": 0,
        "bytes_saved": 0,
    }

    for path in paths:
        cfg = DATASET_CONFIGS.get(path.name)
        if cfg is None or not path.exists():
            continue
        report = convert_file(path, cfg, apply=args.apply)
        reports.append(report)
        totals["files"] += 1
        totals["changed_files"] += 1 if report["changed"] else 0
        totals["bytes_before"] += int(report["bytes_before"])
        totals["bytes_after"] += int(report["bytes_after"])
        totals["bytes_saved"] += int(report["bytes_saved"])

    print(json.dumps({"apply": args.apply, "totals": totals, "reports": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
