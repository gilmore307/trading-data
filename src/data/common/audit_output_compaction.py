from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.data.common.storage_paths import market_tape_root

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = market_tape_root() / "1_long_retention"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def option_snapshot_score(row: dict[str, Any]) -> tuple[int, int, int, str]:
    snapshot = row.get("snapshot", {})
    latest_quote = snapshot.get("latestQuote", {}) if isinstance(snapshot, dict) else {}
    latest_trade = snapshot.get("latestTrade", {}) if isinstance(snapshot, dict) else {}
    minute_bar = snapshot.get("minuteBar", {}) if isinstance(snapshot, dict) else {}
    daily_bar = snapshot.get("dailyBar", {}) if isinstance(snapshot, dict) else {}

    richness = sum(
        1
        for value in [latest_quote, latest_trade, minute_bar, daily_bar]
        if isinstance(value, dict) and value
    )
    quote_t = str(latest_quote.get("t") or "")
    status = str(latest_quote.get("c") or "")
    status_rank = 0 if status.strip() else -1
    return (richness, status_rank, len(json.dumps(row, ensure_ascii=False, sort_keys=True)), quote_t)


def compact_options_snapshots(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        option_symbol = str(row.get("option_symbol") or "")
        ts = row.get("ts")
        if not option_symbol or ts is None:
            continue
        groups[(option_symbol, int(ts))].append(row)

    kept: list[dict[str, Any]] = []
    duplicate_groups = 0
    removed_rows = 0
    exact_duplicate_rows = 0

    for key in sorted(groups.keys(), key=lambda item: (item[1], item[0])):
        bucket = groups[key]
        if len(bucket) > 1:
            duplicate_groups += 1
            removed_rows += len(bucket) - 1
            exact_duplicate_rows += len(bucket) - len({json.dumps(r, ensure_ascii=False, sort_keys=True) for r in bucket})
        best = max(bucket, key=option_snapshot_score)
        kept.append(best)

    stats = {
        "row_count_before": len(rows),
        "row_count_after": len(kept),
        "duplicate_groups": duplicate_groups,
        "removed_rows": removed_rows,
        "exact_duplicate_rows": exact_duplicate_rows,
    }
    return kept, stats


def analyze_file(path: Path, *, apply: bool) -> dict[str, Any]:
    rows = load_jsonl(path)
    rel = str(path.relative_to(ROOT))
    before_bytes = path.stat().st_size

    if path.name == "options_snapshots.jsonl":
        kept, stats = compact_options_snapshots(rows)
        changed = len(kept) != len(rows)
    else:
        kept = rows
        stats = {
            "row_count_before": len(rows),
            "row_count_after": len(rows),
            "duplicate_groups": 0,
            "removed_rows": 0,
            "exact_duplicate_rows": len(rows) - len({json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows}),
        }
        changed = False

    after_bytes_estimate = sum(len(json.dumps(row, ensure_ascii=False)) + 1 for row in kept)

    if apply and changed:
        with path.open("w", encoding="utf-8") as f:
            for row in kept:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        after_bytes = path.stat().st_size
    else:
        after_bytes = after_bytes_estimate

    return {
        "path": rel,
        "dataset": path.name,
        "changed": changed,
        "bytes_before": before_bytes,
        "bytes_after": after_bytes,
        "bytes_saved": max(before_bytes - after_bytes, 0),
        **stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and optionally compact tracked trading-data output files.")
    parser.add_argument("--apply", action="store_true", help="rewrite supported datasets in place")
    parser.add_argument("--only", nargs="*", default=None, help="limit to specific relative paths under trading-storage/2_market_tape/1_long_retention/")
    args = parser.parse_args()

    paths: list[Path]
    if args.only:
        paths = [DATA_ROOT / rel for rel in args.only]
    else:
        paths = sorted(DATA_ROOT.rglob("*.jsonl"))

    reports = []
    totals = {
        "files": 0,
        "changed_files": 0,
        "bytes_before": 0,
        "bytes_after": 0,
        "bytes_saved": 0,
        "row_count_before": 0,
        "row_count_after": 0,
        "removed_rows": 0,
    }

    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        report = analyze_file(path, apply=args.apply)
        reports.append(report)
        totals["files"] += 1
        totals["changed_files"] += 1 if report["changed"] else 0
        totals["bytes_before"] += int(report["bytes_before"])
        totals["bytes_after"] += int(report["bytes_after"])
        totals["bytes_saved"] += int(report["bytes_saved"])
        totals["row_count_before"] += int(report["row_count_before"])
        totals["row_count_after"] += int(report["row_count_after"])
        totals["removed_rows"] += int(report["removed_rows"])

    print(json.dumps({"apply": args.apply, "totals": totals, "reports": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
