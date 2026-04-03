from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PYTHON = os.getenv("PYTHON_BIN", "python3")


def run(cmd: list[str], *, env: dict[str, str] | None = None, required: bool = True) -> bool:
    print(json.dumps({"run": cmd, "required": required}, ensure_ascii=False))
    try:
        subprocess.run(cmd, check=True, cwd=ROOT, env=env)
        return True
    except subprocess.CalledProcessError:
        if required:
            raise
        print(json.dumps({"warning": "non_required_step_failed", "cmd": cmd}, ensure_ascii=False))
        return False


def current_month_start_iso() -> str:
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, 1, tzinfo=UTC)
    return start.isoformat().replace("+00:00", "Z")


def current_time_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_symbol_specs(symbol: str | None, asset_class: str | None, symbols_file: Path | None) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    if symbol and asset_class:
        specs.append({"symbol": symbol, "asset_class": asset_class})
    if symbols_file:
        payload = json.loads(symbols_file.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("symbols file must contain a JSON array")
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("each symbols file entry must be an object")
            item_symbol = item.get("symbol")
            item_asset_class = item.get("asset_class")
            if not item_symbol or item_asset_class not in {"stocks", "crypto"}:
                raise ValueError("each entry must provide symbol and asset_class in {stocks, crypto}")
            specs.append({"symbol": str(item_symbol), "asset_class": str(item_asset_class)})
    if not specs:
        raise ValueError("provide either --symbol with --asset-class, or --symbols-file")

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for spec in specs:
        key = (spec["symbol"], spec["asset_class"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(spec)
    return deduped


def update_symbol(*, symbol: str, asset_class: str, start: str, end: str, limit: int, with_news: bool, with_options: bool, env: dict[str, str]) -> dict[str, object]:
    steps: list[dict[str, object]] = []

    effective_with_news = with_news and asset_class == "stocks"
    effective_with_options = with_options and asset_class == "stocks"

    step_cmds: list[tuple[str, list[str], bool]] = [
        (
            "bars",
            [
                PYTHON,
                "src/data/alpaca/fetch_historical_bars.py",
                "--asset-class", asset_class,
                "--symbol", symbol,
                "--start", start,
                "--end", end,
                "--limit", str(limit),
                "--resume",
            ],
            True,
        ),
        (
            "quotes",
            [
                PYTHON,
                "src/data/alpaca/fetch_historical_quotes.py",
                "--asset-class", asset_class,
                "--symbol", symbol,
                "--start", start,
                "--end", end,
                "--limit", str(limit),
                "--resume",
            ],
            True,
        ),
        (
            "trades",
            [
                PYTHON,
                "src/data/alpaca/fetch_historical_trades.py",
                "--asset-class", asset_class,
                "--symbol", symbol,
                "--start", start,
                "--end", end,
                "--limit", str(limit),
                "--resume",
            ],
            True,
        ),
    ]

    if effective_with_news:
        step_cmds.append((
            "news",
            [
                PYTHON,
                "src/data/alpaca/fetch_news.py",
                "--symbol", symbol,
                "--start", start,
                "--end", end,
                "--limit", "50",
                "--resume",
            ],
            False,
        ))

    if effective_with_options:
        step_cmds.append((
            "options_snapshots",
            [
                PYTHON,
                "src/data/alpaca/fetch_option_snapshots.py",
                "--underlying-symbol", symbol,
                "--limit", "100",
                "--resume",
            ],
            False,
        ))

    for step_name, cmd, required in step_cmds:
        ok = run(cmd, env=env, required=required)
        steps.append({"step": step_name, "required": required, "ok": ok})

    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "with_news": effective_with_news,
        "with_options": effective_with_options,
        "steps": steps,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Update current-month Alpaca datasets for one or more symbols.")
    parser.add_argument("--symbol")
    parser.add_argument("--asset-class", choices=["stocks", "crypto"])
    parser.add_argument("--symbols-file", type=Path)
    parser.add_argument("--with-news", action="store_true")
    parser.add_argument("--with-options", action="store_true")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    specs = load_symbol_specs(args.symbol, args.asset_class, args.symbols_file)
    start = current_month_start_iso()
    end = current_time_iso()
    env = os.environ.copy()

    results = []
    for spec in specs:
        results.append(update_symbol(
            symbol=spec["symbol"],
            asset_class=spec["asset_class"],
            start=start,
            end=end,
            limit=args.limit,
            with_news=args.with_news,
            with_options=args.with_options,
            env=env,
        ))

    print(json.dumps({
        "start": start,
        "end": end,
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
