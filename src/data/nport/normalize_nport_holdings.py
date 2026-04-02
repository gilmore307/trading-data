from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = ROOT / "context" / "etf_holdings"


def pick(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def normalize_record(record: dict[str, Any], *, etf_symbol: str, as_of_date: str | None = None) -> dict[str, Any] | None:
    constituent_symbol = pick(record, "constituent_symbol", "ticker", "issuer_ticker", "symbol")
    constituent_name = pick(record, "constituent_name", "name", "issuer_name", "investment_name")
    weight = pick(record, "weight_percent", "pct_value", "percent_value", "weight")
    effective_as_of = as_of_date or pick(record, "as_of_date", "report_date", "period_end")

    if constituent_symbol in (None, "") and constituent_name in (None, ""):
        return None

    return {
        "etf_symbol": etf_symbol,
        "as_of_date": effective_as_of,
        "constituent_symbol": constituent_symbol,
        "constituent_name": constituent_name,
        "weight_percent": weight,
    }


def load_input(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def load_existing(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("holdings"), list):
        return payload["holdings"]
    return []


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (
            row.get("etf_symbol"),
            row.get("as_of_date"),
            row.get("constituent_symbol"),
            row.get("constituent_name"),
            row.get("weight_percent"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize raw/candidate N-PORT holdings-like records into the compact ETF holdings schema.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--etf-symbol", required=True)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    payload = load_input(args.input)
    if isinstance(payload, dict):
        if isinstance(payload.get("holdings"), list):
            records = payload["holdings"]
        elif isinstance(payload.get("data"), list):
            records = payload["data"]
        else:
            records = [payload]
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("unsupported input payload")

    normalized = []
    for record in records:
        if not isinstance(record, dict):
            continue
        row = normalize_record(record, etf_symbol=args.etf_symbol, as_of_date=args.as_of_date)
        if row:
            normalized.append(row)

    output_path = args.output or (DEFAULT_OUTPUT_DIR / f"{args.etf_symbol}.json")
    existing = load_existing(output_path)
    merged = dedupe(existing + normalized)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "etf_symbol": args.etf_symbol,
        "holdings": merged,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "input": str(args.input),
        "output": str(output_path),
        "new_rows": len(normalized),
        "total_rows": len(merged),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
