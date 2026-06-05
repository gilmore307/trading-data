"""CLI runner for the m09_option_expression_data_acquisition data source."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run, run_many


def _task_key_paths_from_manifest(path: Path) -> list[Path]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        values = payload.get("task_key_paths") or payload.get("task_keys") or []
    else:
        values = []
    paths = [Path(str(item)) for item in values if str(item)]
    if not paths:
        raise ValueError("task-key manifest must contain task_key_paths")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m data_source.m09_option_expression_data_acquisition")
    parser.add_argument("task_key", nargs="?", type=Path, help="Path to a m09_option_expression_data_acquisition task key JSON file")
    parser.add_argument("--run-id")
    parser.add_argument("--task-key-manifest", type=Path, help="JSON manifest with task_key_paths for one batch process")
    parser.add_argument("--batch-run-id", help="Run id suffix shared by task-key manifest entries")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args(argv)
    if args.task_key_manifest is not None:
        batch_run_id = args.batch_run_id or args.run_id
        if not batch_run_id:
            parser.error("--batch-run-id or --run-id is required with --task-key-manifest")
        task_keys = [json.loads(path.read_text(encoding="utf-8")) for path in _task_key_paths_from_manifest(args.task_key_manifest)]
        summary = run_many(task_keys, batch_run_id=batch_run_id, continue_on_error=args.continue_on_error)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if int(summary["failed_count"]) == 0 else 1
    if args.task_key is None or not args.run_id:
        parser.error("task_key and --run-id are required unless --task-key-manifest is used")
    result = run(json.loads(args.task_key.read_text(encoding="utf-8")), run_id=args.run_id)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0 if result.status == "succeeded" else 1

if __name__ == "__main__":
    raise SystemExit(main())
