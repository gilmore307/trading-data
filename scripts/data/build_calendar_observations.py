#!/usr/bin/env python3
"""Build unified calendar observations from accepted calendar source artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data_runtime.calendar_observation import (
    build_market_session_observations,
    build_option_expiry_observations,
    release_calendar_observations,
    trading_economics_observations,
    write_observations,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True, help="Exclusive end date.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--include-market-sessions", action="store_true")
    parser.add_argument("--include-option-expiry", action="store_true")
    parser.add_argument("--release-calendar", type=Path, action="append", default=[])
    parser.add_argument("--trading-economics-calendar", type=Path, action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    observations = []
    if args.include_market_sessions:
        observations.extend(build_market_session_observations(args.start_date, args.end_date))
    if args.include_option_expiry:
        observations.extend(build_option_expiry_observations(args.start_date, args.end_date))
    if args.release_calendar:
        observations.extend(release_calendar_observations(args.release_calendar))
    if args.trading_economics_calendar:
        observations.extend(trading_economics_observations(args.trading_economics_calendar))
    receipt = write_observations(observations, args.output_dir)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
