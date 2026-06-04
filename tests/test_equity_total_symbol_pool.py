from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.data.build_equity_total_symbol_pool import build_pool
from scripts.data.fetch_tradingview_equity_screener import fetch_rows


class EquityTotalSymbolPoolTests(unittest.TestCase):
    def test_build_pool_filters_to_optionable_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tradingview = root / "tradingview.csv"
            holdings = root / "holdings.csv"
            optionable = root / "optionable.txt"
            _write_csv(
                tradingview,
                ["Symbol", "Name", "Sector", "Volume", "Market Cap"],
                [
                    {"Symbol": "NVDA", "Name": "NVIDIA Corporation", "Sector": "Technology", "Volume": "90M", "Market Cap": "4T"},
                    {"Symbol": "BRK.A", "Name": "Berkshire Hathaway Inc.", "Sector": "Finance", "Volume": "500K", "Market Cap": "800B"},
                    {"Symbol": "AACBU", "Name": "Example Units", "Sector": "Finance", "Volume": "1B", "Market Cap": "0"},
                ],
            )
            _write_csv(holdings, ["holding_symbol"], [{"holding_symbol": "AAPL"}, {"holding_symbol": "BRK.A"}])
            optionable.write_text("AAPL\nNVDA\n", encoding="utf-8")

            rows, receipt = build_pool(
                tradingview_csvs=[tradingview],
                layer2_holdings_csvs=[holdings],
                optionable_symbols_file=optionable,
                as_of_date="2026-06-04",
            )

        by_symbol = {row.symbol: row for row in rows}
        self.assertEqual(set(by_symbol), {"AAPL", "NVDA"})
        self.assertTrue(by_symbol["AAPL"].in_layer2_etf_holdings)
        self.assertTrue(by_symbol["NVDA"].in_market_cap_top100)
        self.assertTrue(by_symbol["NVDA"].in_recent_week_volume_top100)
        self.assertNotIn("BRK.A", by_symbol)
        self.assertEqual(receipt["excluded_non_optionable_or_unverified_count"], 1)

    def test_cli_writes_pool_and_symbols_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tradingview = root / "tradingview.csv"
            optionable = root / "optionable.txt"
            output_csv = root / "pool.csv"
            symbols_txt = root / "pool.symbols.txt"
            receipt = root / "pool.receipt.json"
            _write_csv(
                tradingview,
                ["Ticker", "Name", "Sector", "Volume", "Market Cap"],
                [
                    {"Ticker": "META", "Name": "Meta Platforms", "Sector": "Communication Services", "Volume": "12,000,000", "Market Cap": "1.8T"},
                    {"Ticker": "BRK.A", "Name": "Berkshire Hathaway", "Sector": "Finance", "Volume": "1,000", "Market Cap": "800B"},
                ],
            )
            optionable.write_text("META\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/data/build_equity_total_symbol_pool.py",
                    "--tradingview-csv",
                    str(tradingview),
                    "--optionable-symbols-file",
                    str(optionable),
                    "--as-of-date",
                    "2026-06-04",
                    "--output-csv",
                    str(output_csv),
                    "--symbols-txt",
                    str(symbols_txt),
                    "--receipt",
                    str(receipt),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            stdout = json.loads(completed.stdout)
            self.assertEqual(stdout["selected_symbol_count"], 1)
            self.assertEqual(symbols_txt.read_text(encoding="utf-8"), "META\n")
            with output_csv.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["symbol"], "META")
            self.assertEqual(rows[0]["sector"], "Communication Services")
            self.assertTrue(receipt.exists())

    def test_cli_can_include_unknown_optionability_in_symbols_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tradingview = root / "tradingview.csv"
            output_csv = root / "pool.csv"
            symbols_txt = root / "pool.symbols.txt"
            receipt = root / "pool.receipt.json"
            _write_csv(
                tradingview,
                ["Ticker", "Name", "Sector", "Volume", "Market Cap"],
                [{"Ticker": "MSFT", "Name": "Microsoft", "Sector": "Technology", "Volume": "10M", "Market Cap": "4T"}],
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/data/build_equity_total_symbol_pool.py",
                    "--tradingview-csv",
                    str(tradingview),
                    "--as-of-date",
                    "2026-06-04",
                    "--allow-unknown-optionability",
                    "--symbols-include-unknown-optionability",
                    "--output-csv",
                    str(output_csv),
                    "--symbols-txt",
                    str(symbols_txt),
                    "--receipt",
                    str(receipt),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            stdout = json.loads(completed.stdout)
            self.assertEqual(stdout["symbols_txt_optionability_statuses"], ["accepted_optionable", "uncertain_verify_before_use"])
            self.assertEqual(symbols_txt.read_text(encoding="utf-8"), "MSFT\n")

    def test_tradingview_fetch_rows_merges_volume_and_market_cap_scans(self) -> None:
        original = sys.modules["scripts.data.fetch_tradingview_equity_screener"]._post_scan

        def fake_post_scan(payload: dict, *, timeout_seconds: float) -> dict:
            sort_by = payload["sort"]["sortBy"]
            if sort_by == "volume":
                return {
                    "totalCount": 2,
                    "data": [
                        {"s": "NASDAQ:AAPL", "d": ["AAPL", "Apple Inc.", "stock", "common", "NASDAQ", "Technology", 1000, 3000]},
                    ],
                }
            return {
                "totalCount": 2,
                "data": [
                    {"s": "NASDAQ:MSFT", "d": ["MSFT", "Microsoft Corporation", "stock", "common", "NASDAQ", "Technology", 800, 4000]},
                    {"s": "NASDAQ:AAPL", "d": ["AAPL", "Apple Inc.", "stock", "common", "NASDAQ", "Technology", 1000, 3000]},
                ],
            }

        try:
            sys.modules["scripts.data.fetch_tradingview_equity_screener"]._post_scan = fake_post_scan
            rows, receipt = fetch_rows(per_rank_limit=100, timeout_seconds=1, as_of_date="2026-06-04")
        finally:
            sys.modules["scripts.data.fetch_tradingview_equity_screener"]._post_scan = original

        by_symbol = {row["Symbol"]: row for row in rows}
        self.assertEqual(set(by_symbol), {"AAPL", "MSFT"})
        self.assertEqual(by_symbol["AAPL"]["Included By"], "market_cap_top;recent_week_volume_top")
        self.assertEqual(by_symbol["MSFT"]["Included By"], "market_cap_top")
        self.assertEqual(receipt["selected_symbol_count"], 2)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
