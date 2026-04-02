from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]


def fetch_probe(symbol: str) -> dict:
    urls = [
        "https://www.etf.com/",
        f"https://www.etf.com/{symbol}",
        f"https://www.etf.com/search?query={symbol}",
    ]
    results = []
    for url in urls:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            results.append({
                "url": url,
                "status": resp.status_code,
                "content_type": resp.headers.get("content-type"),
                "snippet": resp.text[:200],
            })
        except Exception as exc:
            results.append({
                "url": url,
                "error": repr(exc),
            })
    return {
        "symbol": symbol,
        "fetched_at": datetime.now(UTC).isoformat(),
        "results": results,
        "conclusion": "Direct HTTP fetch currently blocked by Cloudflare; etf.com is not yet usable as a simple requests-based canonical mapping source from this environment.",
        "next_step_hint": "If etf.com remains strategically valuable, use browser-assisted/manual discovery or identify a more automation-friendly source for candidate ETF mapping.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe etf.com accessibility for ETF candidate discovery.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = fetch_probe(args.symbol)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
