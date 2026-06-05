#!/usr/bin/env python3
"""Freeze a static historical replay candidate universe from the current pools."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_POOL = Path("/root/projects/trading-storage/main/shared/equity_total_symbol_pool.csv")
DEFAULT_OUTPUT_CSV = Path("/root/projects/trading-storage/main/shared/historical_candidate_universe.csv")
DEFAULT_SYMBOLS_TXT = Path("/root/projects/trading-storage/main/shared/historical_candidate_universe.symbols.txt")
DEFAULT_RECEIPT = Path("/root/projects/trading-storage/storage/02_control_plane/runtime/equity_total_symbol_pool/historical_candidate_universe_build_receipt.json")
DEFAULT_UNIVERSE_POLICY_REF = "fixed_current_realtime_pool_snapshot_for_historical_replay"
CORE_CRYPTO_TARGETS = ("BTC", "ETH", "SOL")

TRADINGVIEW_SECTOR_TO_LAYER2_CONTEXT = {
    "Communication Services": "XLC",
    "Commercial Services": "XLI",
    "Communications": "XLC",
    "Consumer Durables": "XLY",
    "Consumer Non-Durables": "XLP",
    "Consumer Services": "XLY",
    "Distribution Services": "XLI",
    "Electronic Technology": "XLK",
    "Energy Minerals": "XLE",
    "Finance": "XLF",
    "Health Services": "XLV",
    "Health Technology": "XLV",
    "Industrial Services": "XLI",
    "Non-Energy Minerals": "XLB",
    "Process Industries": "XLB",
    "Producer Manufacturing": "XLI",
    "Retail Trade": "XLY",
    "Technology": "XLK",
    "Technology Services": "XLK",
    "Transportation": "XLI",
    "Utilities": "XLU",
}

CRYPTO_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
}
SYMBOL_LAYER2_CONTEXT_OVERRIDES = {
    "HUT": ("BKCH", "crypto_related_equity_context_override"),
    "FDXF": ("XLI", "transportation_equity_context_override"),
}

OUTPUT_FIELDS = [
    "symbol",
    "target_ref",
    "asset_class",
    "instrument_type",
    "name",
    "tradingview_sector",
    "layer2_context_symbol",
    "layer2_context_method",
    "optionable_underlying_status",
    "replay_candidate_status",
    "replay_candidate_reason",
    "source_pool_as_of_date",
    "in_dollar_volume_top300",
    "in_market_cap_top300",
    "dollar_volume_rank",
    "market_cap_rank",
    "source_refs",
    "freeze_as_of_date",
    "universe_policy_ref",
]


@dataclass(frozen=True)
class HistoricalCandidateRow:
    symbol: str
    target_ref: str
    asset_class: str
    instrument_type: str
    name: str
    tradingview_sector: str
    layer2_context_symbol: str
    layer2_context_method: str
    optionable_underlying_status: str
    replay_candidate_status: str
    replay_candidate_reason: str
    source_pool_as_of_date: str
    in_dollar_volume_top300: str
    in_market_cap_top300: str
    dollar_volume_rank: str
    market_cap_rank: str
    source_refs: str
    freeze_as_of_date: str
    universe_policy_ref: str = DEFAULT_UNIVERSE_POLICY_REF

    def to_csv_row(self) -> dict[str, str]:
        return {field: str(getattr(self, field)) for field in OUTPUT_FIELDS}


def _clean_symbol(value: str) -> str:
    return str(value or "").strip().upper()


def _valid_symbol(symbol: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{str(key): str(value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def _layer2_context_for_equity(symbol: str, sector: str) -> tuple[str, str]:
    override = SYMBOL_LAYER2_CONTEXT_OVERRIDES.get(symbol)
    if override:
        return override
    context = TRADINGVIEW_SECTOR_TO_LAYER2_CONTEXT.get(str(sector or "").strip())
    if not context:
        raise ValueError(f"unmapped TradingView sector for historical candidate universe: {sector!r}")
    return context, "tradingview_sector_to_spdr_anchor"


def _equity_rows(*, source_pool_csv: Path, freeze_as_of_date: str, universe_policy_ref: str) -> tuple[list[HistoricalCandidateRow], int]:
    rows: list[HistoricalCandidateRow] = []
    seen: set[str] = set()
    source_rows = _read_csv(source_pool_csv)
    for raw in source_rows:
        symbol = _clean_symbol(raw.get("symbol"))
        if not symbol or symbol in seen or not _valid_symbol(symbol):
            continue
        if str(raw.get("pool_membership_status") or "").strip().lower() != "active":
            continue
        tradingview_sector = str(raw.get("sector") or "")
        layer2_context_symbol, layer2_context_method = _layer2_context_for_equity(symbol, tradingview_sector)
        rows.append(
            HistoricalCandidateRow(
                symbol=symbol,
                target_ref=symbol,
                asset_class="us_equity",
                instrument_type="common_stock_or_optionable_underlying",
                name=str(raw.get("name") or ""),
                tradingview_sector=tradingview_sector,
                layer2_context_symbol=layer2_context_symbol,
                layer2_context_method=layer2_context_method,
                optionable_underlying_status=str(raw.get("optionable_underlying_status") or ""),
                replay_candidate_status="active",
                replay_candidate_reason="active_fixed_current_realtime_pool_snapshot",
                source_pool_as_of_date=str(raw.get("as_of_date") or ""),
                in_dollar_volume_top300=str(raw.get("in_dollar_volume_top300") or "false").lower(),
                in_market_cap_top300=str(raw.get("in_market_cap_top300") or "false").lower(),
                dollar_volume_rank=str(raw.get("dollar_volume_rank") or ""),
                market_cap_rank=str(raw.get("market_cap_rank") or ""),
                source_refs=str(raw.get("source_refs") or ""),
                freeze_as_of_date=freeze_as_of_date,
                universe_policy_ref=universe_policy_ref,
            )
        )
        seen.add(symbol)
    return rows, len(source_rows)


def _crypto_rows(*, freeze_as_of_date: str, universe_policy_ref: str, crypto_targets: tuple[str, ...]) -> list[HistoricalCandidateRow]:
    rows: list[HistoricalCandidateRow] = []
    for symbol in crypto_targets:
        rows.append(
            HistoricalCandidateRow(
                symbol=symbol,
                target_ref=symbol,
                asset_class="crypto_spot",
                instrument_type="spot_crypto",
                name=CRYPTO_NAMES.get(symbol, symbol),
                tradingview_sector="Crypto",
                layer2_context_symbol="BKCH",
                layer2_context_method="crypto_business_context_anchor_exception",
                optionable_underlying_status="not_applicable",
                replay_candidate_status="active",
                replay_candidate_reason="active_core_crypto_target",
                source_pool_as_of_date="",
                in_dollar_volume_top300="false",
                in_market_cap_top300="false",
                dollar_volume_rank="",
                market_cap_rank="",
                source_refs="fixed_core_crypto_target",
                freeze_as_of_date=freeze_as_of_date,
                universe_policy_ref=universe_policy_ref,
            )
        )
    return rows


def build_universe(
    *,
    source_pool_csv: Path,
    freeze_as_of_date: str,
    universe_policy_ref: str = DEFAULT_UNIVERSE_POLICY_REF,
    crypto_targets: tuple[str, ...] = CORE_CRYPTO_TARGETS,
) -> tuple[list[HistoricalCandidateRow], dict[str, Any]]:
    rows, source_row_count = _equity_rows(
        source_pool_csv=source_pool_csv,
        freeze_as_of_date=freeze_as_of_date,
        universe_policy_ref=universe_policy_ref,
    )
    rows.extend(
        _crypto_rows(
            freeze_as_of_date=freeze_as_of_date,
            universe_policy_ref=universe_policy_ref,
            crypto_targets=crypto_targets,
        )
    )
    rows.sort(
        key=lambda row: (
            0 if row.asset_class == "us_equity" else 1,
            int(row.market_cap_rank or "10000"),
            int(row.dollar_volume_rank or "10000"),
            row.symbol,
        )
    )
    receipt = {
        "contract_type": "historical_candidate_universe_build_receipt",
        "source_pool_csv": str(source_pool_csv),
        "freeze_as_of_date": freeze_as_of_date,
        "universe_policy_ref": universe_policy_ref,
        "source_row_count": source_row_count,
        "active_candidate_count": len(rows),
        "asset_class_counts": {
            "us_equity": sum(1 for row in rows if row.asset_class == "us_equity"),
            "crypto_spot": sum(1 for row in rows if row.asset_class == "crypto_spot"),
        },
        "layer2_context_symbols": sorted({row.layer2_context_symbol for row in rows}),
        "boundary_note": "This is a fixed historical replay candidate universe seeded from the current realtime total-symbol pool plus core crypto targets. It is stable replay scope, not point-in-time historical market-wide ranking evidence.",
    }
    return rows, receipt


def write_outputs(rows: list[HistoricalCandidateRow], *, output_csv: Path, symbols_txt: Path, receipt_path: Path, receipt: dict[str, Any]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(row.to_csv_row() for row in rows)
    symbols_txt.parent.mkdir(parents=True, exist_ok=True)
    symbols_txt.write_text("".join(f"{row.symbol}\n" for row in rows), encoding="utf-8")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps({**receipt, "output_csv": str(output_csv), "symbols_txt": str(symbols_txt)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pool-csv", type=Path, default=DEFAULT_SOURCE_POOL)
    parser.add_argument("--freeze-as-of-date", default=date.today().isoformat())
    parser.add_argument("--universe-policy-ref", default=DEFAULT_UNIVERSE_POLICY_REF)
    parser.add_argument("--crypto-target", action="append", default=list(CORE_CRYPTO_TARGETS))
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--symbols-txt", type=Path, default=DEFAULT_SYMBOLS_TXT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, receipt = build_universe(
        source_pool_csv=args.source_pool_csv,
        freeze_as_of_date=args.freeze_as_of_date,
        universe_policy_ref=args.universe_policy_ref,
        crypto_targets=tuple(_clean_symbol(symbol) for symbol in args.crypto_target),
    )
    write_outputs(rows, output_csv=args.output_csv, symbols_txt=args.symbols_txt, receipt_path=args.receipt, receipt=receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
