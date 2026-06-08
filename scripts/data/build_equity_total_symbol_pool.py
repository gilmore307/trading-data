#!/usr/bin/env python3
"""Build the reviewed realtime equity total-symbol pool from TradingView inputs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

DEFAULT_OUTPUT_CSV = Path("/root/projects/trading-storage/main/shared/equity_total_symbol_pool.csv")
DEFAULT_SYMBOLS_TXT = Path("/root/projects/trading-storage/main/shared/equity_total_symbol_pool.symbols.txt")
DEFAULT_RECEIPT = Path("/root/projects/trading-storage/storage/02_control_plane/runtime/equity_total_symbol_pool/build_receipt.json")
DEFAULT_RANK_LIMIT = 300

OUTPUT_FIELDS = [
    "symbol",
    "name",
    "sector",
    "optionable_underlying_status",
    "pool_membership_status",
    "pool_membership_reason",
    "in_dollar_volume_top300",
    "in_market_cap_top300",
    "dollar_volume_rank",
    "market_cap_rank",
    "source_refs",
    "as_of_date",
]

SYMBOL_FIELDS = ("symbol", "ticker", "Symbol", "Ticker", "Ticker symbol")
NAME_FIELDS = ("name", "Name", "description", "Description", "Company Name")
SECTOR_FIELDS = ("sector", "Sector")
DOLLAR_VOLUME_FIELDS = ("dollar_volume", "Dollar Volume", "Value Traded", "Value.Traded")
MARKET_CAP_FIELDS = ("market_cap", "marketCap", "Market Cap", "Market capitalization")


@dataclass
class PoolRow:
    symbol: str
    name: str = ""
    sector: str = ""
    optionable_underlying_status: str = "uncertain_verify_before_use"
    pool_membership_status: str = "inactive"
    pool_membership_reason: str = "not_evaluated"
    in_dollar_volume_top300: bool = False
    in_market_cap_top300: bool = False
    dollar_volume_rank: int | None = None
    market_cap_rank: int | None = None
    source_refs: set[str] = field(default_factory=set)
    as_of_date: str = ""

    def to_csv_row(self) -> dict[str, str]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "sector": self.sector,
            "optionable_underlying_status": self.optionable_underlying_status,
            "pool_membership_status": self.pool_membership_status,
            "pool_membership_reason": self.pool_membership_reason,
            "in_dollar_volume_top300": str(self.in_dollar_volume_top300).lower(),
            "in_market_cap_top300": str(self.in_market_cap_top300).lower(),
            "dollar_volume_rank": "" if self.dollar_volume_rank is None else str(self.dollar_volume_rank),
            "market_cap_rank": "" if self.market_cap_rank is None else str(self.market_cap_rank),
            "source_refs": ";".join(sorted(self.source_refs)),
            "as_of_date": self.as_of_date,
        }


def _field(row: dict[str, str], names: Iterable[str]) -> str:
    lower = {key.lower().strip(): value for key, value in row.items()}
    for name in names:
        if name in row and str(row[name]).strip():
            return str(row[name]).strip()
        value = lower.get(name.lower().strip())
        if value and str(value).strip():
            return str(value).strip()
    return ""


def _clean_symbol(value: str) -> str:
    symbol = value.strip().upper()
    symbol = symbol.removeprefix("NASDAQ:").removeprefix("NYSE:").removeprefix("AMEX:")
    return symbol


def _is_common_stock_like(row: dict[str, str]) -> bool:
    text = " ".join(str(value or "") for value in row.values()).lower()
    blocked = (" etf", " fund", " warrant", " right", " unit", " preferred", " note", " bond")
    return not any(pattern in f" {text}" for pattern in blocked)


def _number(value: str) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("$", "")
    if not text or text in {"-", "—", "N/A"}:
        return None
    multiplier = 1.0
    suffix = text[-1:].upper()
    if suffix in {"K", "M", "B", "T"}:
        multiplier = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[suffix]
        text = text[:-1]
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text:
        return None
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{str(key): str(value or "") for key, value in row.items()} for row in csv.DictReader(handle)]


def _read_symbols(path: Path | None) -> set[str]:
    if path is None:
        return set()
    text = path.read_text(encoding="utf-8")
    return {_clean_symbol(raw) for raw in re.split(r"[\s,;]+", text) if raw.strip()}


def build_pool(
    *,
    tradingview_csvs: list[Path],
    optionable_symbols_file: Path | None,
    non_optionable_symbols_file: Path | None = None,
    as_of_date: str,
    rank_limit: int = DEFAULT_RANK_LIMIT,
    allow_unknown_optionability: bool = False,
) -> tuple[list[PoolRow], dict[str, Any]]:
    rows_by_symbol: dict[str, PoolRow] = {}
    metrics: dict[str, dict[str, float | None]] = {}

    for path in tradingview_csvs:
        for raw in _read_csv(path):
            symbol = _clean_symbol(_field(raw, SYMBOL_FIELDS))
            if not symbol or not _is_common_stock_like(raw):
                continue
            row = rows_by_symbol.setdefault(symbol, PoolRow(symbol=symbol, as_of_date=as_of_date))
            row.name = row.name or _field(raw, NAME_FIELDS)
            row.sector = row.sector or _field(raw, SECTOR_FIELDS)
            row.source_refs.add(f"tradingview_screener_snapshot:{path}")
            metrics.setdefault(symbol, {})["dollar_volume"] = _number(_field(raw, DOLLAR_VOLUME_FIELDS))
            metrics.setdefault(symbol, {})["market_cap"] = _number(_field(raw, MARKET_CAP_FIELDS))

    for rank, symbol in enumerate(_rank_symbols(metrics, "dollar_volume"), start=1):
        row = rows_by_symbol[symbol]
        if rank <= rank_limit:
            row.in_dollar_volume_top300 = True
            row.dollar_volume_rank = rank
    for rank, symbol in enumerate(_rank_symbols(metrics, "market_cap"), start=1):
        row = rows_by_symbol[symbol]
        if rank <= rank_limit:
            row.in_market_cap_top300 = True
            row.market_cap_rank = rank

    optionable = _read_symbols(optionable_symbols_file)
    confirmed_non_optionable = _read_symbols(non_optionable_symbols_file)
    conflicting_symbols = sorted(optionable & confirmed_non_optionable)
    if conflicting_symbols:
        raise ValueError(f"symbols cannot be both optionable and confirmed non-optionable: {', '.join(conflicting_symbols)}")
    for row in rows_by_symbol.values():
        if row.symbol in optionable:
            row.optionable_underlying_status = "accepted_optionable"
        elif row.symbol in confirmed_non_optionable:
            row.optionable_underlying_status = "confirmed_no_listed_options"
        elif allow_unknown_optionability:
            row.optionable_underlying_status = "uncertain_verify_before_use"
        else:
            row.optionable_underlying_status = "no_listed_options_or_unverified"

    for row in rows_by_symbol.values():
        has_current_pool_source = (
            row.in_dollar_volume_top300
            or row.in_market_cap_top300
        )
        if not has_current_pool_source:
            row.pool_membership_status = "inactive"
            row.pool_membership_reason = "inactive_no_current_pool_source_condition"
        elif row.optionable_underlying_status == "confirmed_no_listed_options":
            row.pool_membership_status = "inactive"
            row.pool_membership_reason = "inactive_confirmed_no_listed_options"
        elif row.optionable_underlying_status not in {"accepted_optionable", "uncertain_verify_before_use"}:
            row.pool_membership_status = "inactive"
            row.pool_membership_reason = "inactive_no_listed_options_or_unverified"
        else:
            row.pool_membership_status = "active"
            row.pool_membership_reason = "active_current_pool_source_and_optionability_accepted"

    rows = sorted(
        rows_by_symbol.values(),
        key=lambda row: (
            0 if row.pool_membership_status == "active" else 1,
            row.market_cap_rank or 10_000,
            row.dollar_volume_rank or 10_000,
            row.symbol,
        ),
    )
    selected = [row for row in rows if row.pool_membership_status == "active"]
    receipt = {
        "contract_type": "equity_total_symbol_pool_build_receipt",
        "as_of_date": as_of_date,
        "tradingview_screener_inputs": [str(path) for path in tradingview_csvs],
        "rank_limit": rank_limit,
        "optionable_symbols_file": str(optionable_symbols_file) if optionable_symbols_file else None,
        "non_optionable_symbols_file": str(non_optionable_symbols_file) if non_optionable_symbols_file else None,
        "allow_unknown_optionability": allow_unknown_optionability,
        "input_symbol_count": len(rows_by_symbol),
        "active_symbol_count": len(selected),
        "inactive_symbol_count": len(rows_by_symbol) - len(selected),
        "selected_symbol_count": len(selected),
        "excluded_non_optionable_or_unverified_count": len(rows_by_symbol) - len(selected),
        "confirmed_no_listed_options_count": sum(1 for row in rows if row.optionable_underlying_status == "confirmed_no_listed_options"),
        "boundary_note": "The CSV is the realtime equity total-symbol pool ledger built from TradingView traded-dollar-value and market-cap snapshots; active rows feed the calendar symbols file while inactive rows preserve previously observed but currently unusable symbols. Historical replay must use its frozen candidate-universe table instead of reading this mutable realtime pool directly.",
    }
    return rows, receipt


def _rank_symbols(metrics: dict[str, dict[str, float | None]], field: str) -> list[str]:
    ranked = [(symbol, values.get(field)) for symbol, values in metrics.items()]
    ranked = [(symbol, value) for symbol, value in ranked if value is not None]
    ranked.sort(key=lambda item: (-float(item[1]), item[0]))
    return [symbol for symbol, _value in ranked]


def write_outputs(rows: list[PoolRow], *, output_csv: Path, symbols_txt: Path, receipt_path: Path, receipt: dict[str, Any]) -> None:
    symbol_statuses = set(receipt.get("symbols_txt_optionability_statuses") or ["accepted_optionable"])
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(row.to_csv_row() for row in rows)
    symbols = [
        row.symbol
        for row in rows
        if row.pool_membership_status == "active" and row.optionable_underlying_status in symbol_statuses
    ]
    symbols_txt.write_text("\n".join(symbols) + ("\n" if symbols else ""), encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tradingview-csv", action="append", type=Path, default=[])
    parser.add_argument("--optionable-symbols-file", type=Path, default=None)
    parser.add_argument("--non-optionable-symbols-file", type=Path, default=None)
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--rank-limit", type=int, default=DEFAULT_RANK_LIMIT)
    parser.add_argument("--allow-unknown-optionability", action="store_true")
    parser.add_argument("--symbols-include-unknown-optionability", action="store_true")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--symbols-txt", type=Path, default=DEFAULT_SYMBOLS_TXT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, receipt = build_pool(
        tradingview_csvs=args.tradingview_csv,
        optionable_symbols_file=args.optionable_symbols_file,
        non_optionable_symbols_file=args.non_optionable_symbols_file,
        as_of_date=args.as_of_date,
        rank_limit=args.rank_limit,
        allow_unknown_optionability=args.allow_unknown_optionability,
    )
    symbol_statuses = ["accepted_optionable"]
    if args.symbols_include_unknown_optionability:
        symbol_statuses.append("uncertain_verify_before_use")
    receipt.update(
        {
            "output_csv": str(args.output_csv),
            "symbols_txt": str(args.symbols_txt),
            "symbols_txt_optionability_statuses": symbol_statuses,
        }
    )
    write_outputs(rows, output_csv=args.output_csv, symbols_txt=args.symbols_txt, receipt_path=args.receipt, receipt=receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
