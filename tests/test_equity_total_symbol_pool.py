from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.data.build_equity_total_symbol_pool import build_pool


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


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
