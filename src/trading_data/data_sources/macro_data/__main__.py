"""CLI runner for the macro_data bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m trading_data.data_sources.macro_data")
    parser.add_argument("task_key", type=Path, help="Path to a macro_data task key JSON file")
    parser.add_argument("--run-id", required=True, help="Stable random run id for this invocation")
    args = parser.parse_args(argv)
    task_key = json.loads(args.task_key.read_text(encoding="utf-8"))
    result = run(task_key, run_id=args.run_id)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
