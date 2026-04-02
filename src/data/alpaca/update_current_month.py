from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PYTHON = os.getenv("PYTHON_BIN", "python3")


def run(cmd: list[str], *, env: dict[str, str] | None = None, required: bool = True) -> None:
    print(json.dumps({"run": cmd, "required": required}, ensure_ascii=False))
    try:
        subprocess.run(cmd, check=True, cwd=ROOT, env=env)
    except subprocess.CalledProcessError:
        if required:
            raise
        print(json.dumps({"warning": "non_required_step_failed", "cmd": cmd}, ensure_ascii=False))


def current_month_start_iso() -> str:
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, 1, tzinfo=UTC)
    return start.isoformat().replace("+00:00", "Z")


def current_time_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update current-month Alpaca datasets for one symbol.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--asset-class", choices=["stocks", "crypto"], required=True)
    parser.add_argument("--with-news", action="store_true")
    parser.add_argument("--with-options", action="store_true")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    start = current_month_start_iso()
    end = current_time_iso()
    env = os.environ.copy()

    run([
        PYTHON,
        "src/data/alpaca/fetch_historical_bars.py",
        "--asset-class", args.asset_class,
        "--symbol", args.symbol,
        "--start", start,
        "--end", end,
        "--limit", str(args.limit),
        "--resume",
    ], env=env)

    run([
        PYTHON,
        "src/data/alpaca/fetch_historical_quotes.py",
        "--asset-class", args.asset_class,
        "--symbol", args.symbol,
        "--start", start,
        "--end", end,
        "--limit", str(args.limit),
        "--resume",
    ], env=env)

    run([
        PYTHON,
        "src/data/alpaca/fetch_historical_trades.py",
        "--asset-class", args.asset_class,
        "--symbol", args.symbol,
        "--start", start,
        "--end", end,
        "--limit", str(args.limit),
        "--resume",
    ], env=env)

    if args.with_news:
        run([
            PYTHON,
            "src/data/alpaca/fetch_news.py",
            "--symbol", args.symbol,
            "--start", start,
            "--end", end,
            "--limit", "100",
            "--resume",
        ], env=env, required=False)

    if args.with_options and args.asset_class == "stocks":
        run([
            PYTHON,
            "src/data/alpaca/fetch_option_snapshots.py",
            "--underlying-symbol", args.symbol,
            "--limit", "100",
        ], env=env, required=False)


if __name__ == "__main__":
    main()
