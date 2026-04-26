"""CLI runner for alpaca_quotes_trades."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m trading_data.data_sources.alpaca_quotes_trades")
    parser.add_argument("task_key", type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    result = run(json.loads(args.task_key.read_text(encoding="utf-8")), run_id=args.run_id)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
