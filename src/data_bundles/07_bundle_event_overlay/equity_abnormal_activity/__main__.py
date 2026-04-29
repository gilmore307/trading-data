"""CLI runner for the EventOverlayModel equity abnormal activity detector."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path


def _run(task_key: dict, *, run_id: str):
    module = importlib.import_module(
        "data_bundles.07_bundle_event_overlay.equity_abnormal_activity.pipeline"
    )
    return module.run(task_key, run_id=run_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m data_bundles.07_bundle_event_overlay.equity_abnormal_activity"
    )
    parser.add_argument("task_key", type=Path, help="Path to an equity abnormal activity detector task key JSON file")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    result = _run(json.loads(args.task_key.read_text(encoding="utf-8")), run_id=args.run_id)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
