from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[3]
STATE_PATH = ROOT / "context" / "etf_holdings" / "_nport_state.json"
SEC_DATASET_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets"


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "description": "Local N-PORT monthly availability/capture tracking state for ETF holdings ingestion.",
        "target_month": datetime.now(UTC).strftime("%Y-%m"),
        "last_checked_at": None,
        "current_month_available": False,
        "current_month_captured": False,
        "source_reference": {
            "provider": "sec_nport",
            "dataset_page": SEC_DATASET_PAGE,
            "dataset_candidates": [
                "FUND_REPORTED_HOLDING",
                "IDENTIFIERS",
                "FUND_VAR_INFO",
            ],
        },
        "notes": [],
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def target_token(target_month: str) -> str:
    year, month = target_month.split("-", 1)
    return f"{year}{month}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check SEC N-PORT monthly dataset availability and update local state.")
    parser.add_argument("--state-path", type=Path, default=STATE_PATH)
    parser.add_argument("--target-month", default=None, help="YYYY-MM; defaults to state file target_month")
    parser.add_argument("--dataset-page", default=SEC_DATASET_PAGE)
    args = parser.parse_args()

    state = load_state(args.state_path)
    target_month = args.target_month or state.get("target_month") or datetime.now(UTC).strftime("%Y-%m")
    token = target_token(target_month)

    headers = {
        "User-Agent": "trading-data-nport-check/1.0 (contact: local-workspace)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    outcome: dict[str, Any] = {
        "checked_at": now_iso(),
        "target_month": target_month,
        "dataset_page": args.dataset_page,
    }

    try:
        resp = requests.get(args.dataset_page, headers=headers, timeout=30)
        outcome["status_code"] = resp.status_code
        body = resp.text[:200000]
        available = resp.ok and token in body
        state["current_month_available"] = bool(available)
        if available:
            outcome["availability_signal"] = f"found token {token} in dataset page body"
        else:
            outcome["availability_signal"] = f"token {token} not found in dataset page body"
    except Exception as exc:
        outcome["error"] = str(exc)
        state["current_month_available"] = False

    state["target_month"] = target_month
    state["last_checked_at"] = outcome["checked_at"]
    state.setdefault("source_reference", {})
    state["source_reference"]["dataset_page"] = args.dataset_page
    state["source_reference"]["last_check_outcome"] = outcome
    notes = state.setdefault("notes", [])
    note = "Availability currently uses a coarse page-token check and still needs a stronger filing/package-level detector."
    if note not in notes:
        notes.append(note)

    save_state(args.state_path, state)
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
