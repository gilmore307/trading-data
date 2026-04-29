"""CLI runner for the 08_feed_sec_company_financials feed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from feed_availability.__main__ import DEFAULT_SEC_USER_AGENT
from .pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m data_feed.08_feed_sec_company_financials")
    parser.add_argument("task_key", type=Path, help="Path to a 08_feed_sec_company_financials task key JSON file")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sec-user-agent", default=DEFAULT_SEC_USER_AGENT)
    args = parser.parse_args(argv)
    result = run(json.loads(args.task_key.read_text(encoding="utf-8")), run_id=args.run_id, sec_user_agent=args.sec_user_agent)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
