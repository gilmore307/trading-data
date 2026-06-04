from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from scripts.data.build_equity_total_symbol_pool import build_pool
from scripts.data.build_historical_candidate_universe import build_universe
from scripts.data.fetch_etf_universe_holdings import collect_holdings
from scripts.data.fetch_tradingview_equity_screener import fetch_rows


class EquityTotalSymbolPoolTests(unittest.TestCase):
    def test_build_pool_filters_to_optionable_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tradingview = root / "tradingview.csv"
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
            optionable.write_text("NVDA\n", encoding="utf-8")

            rows, receipt = build_pool(
                tradingview_csvs=[tradingview],
                optionable_symbols_file=optionable,
                as_of_date="2026-06-04",
            )

        by_symbol = {row.symbol: row for row in rows}
        self.assertEqual(set(by_symbol), {"BRK.A", "NVDA"})
        self.assertTrue(by_symbol["NVDA"].in_market_cap_top300)
        self.assertTrue(by_symbol["NVDA"].in_recent_week_volume_top300)
        self.assertEqual(by_symbol["BRK.A"].pool_membership_status, "inactive")
        self.assertEqual(by_symbol["BRK.A"].pool_membership_reason, "inactive_no_listed_options_or_unverified")
        self.assertEqual(
            {row.symbol for row in rows if row.pool_membership_status == "active"},
            {"NVDA"},
        )
        self.assertEqual(receipt["active_symbol_count"], 1)
        self.assertEqual(receipt["inactive_symbol_count"], 1)
        self.assertEqual(receipt["excluded_non_optionable_or_unverified_count"], 1)
        self.assertEqual(receipt["rank_limit"], 300)

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
            self.assertEqual(rows[0]["pool_membership_status"], "active")
            self.assertEqual(rows[1]["symbol"], "BRK.A")
            self.assertEqual(rows[1]["pool_membership_status"], "inactive")
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
            rows, receipt = fetch_rows(per_rank_limit=300, timeout_seconds=1, as_of_date="2026-06-04")
        finally:
            sys.modules["scripts.data.fetch_tradingview_equity_screener"]._post_scan = original

        by_symbol = {row["Symbol"]: row for row in rows}
        self.assertEqual(set(by_symbol), {"AAPL", "MSFT"})
        self.assertEqual(by_symbol["AAPL"]["Included By"], "market_cap_top;recent_week_volume_top")
        self.assertEqual(by_symbol["MSFT"]["Included By"], "market_cap_top")
        self.assertEqual(receipt["selected_symbol_count"], 2)
        self.assertEqual(receipt["per_rank_limit"], 300)

    def test_etf_universe_holdings_collects_layer2_and_dedupes_etf_symbols(self) -> None:
        import scripts.data.fetch_etf_universe_holdings as holdings_module

        original = holdings_module._run_feed

        def fake_run_feed(task_key: dict, *, run_id: str) -> SimpleNamespace:
            saved = Path(task_key["output_root"]) / "runs" / run_id / "saved" / "etf_holding_snapshot.csv"
            rows = [
                {"etf_symbol": task_key["params"]["etf_symbol"], "issuer_name": "test", "as_of_date": "2026-06-04", "holding_symbol": "NVDA", "holding_name": "NVIDIA", "weight": "10", "shares": "", "market_value": "", "cusip": "", "sedol": "", "asset_class": "Equity", "sector_type": "", "source_url": "fixture"},
                {"etf_symbol": task_key["params"]["etf_symbol"], "issuer_name": "test", "as_of_date": "2026-06-04", "holding_symbol": "NVDA", "holding_name": "NVIDIA", "weight": "10", "shares": "", "market_value": "", "cusip": "", "sedol": "", "asset_class": "Equity", "sector_type": "", "source_url": "fixture"},
                {"etf_symbol": task_key["params"]["etf_symbol"], "issuer_name": "test", "as_of_date": "2026-06-04", "holding_symbol": "USD", "holding_name": "Cash", "weight": "1", "shares": "", "market_value": "", "cusip": "", "sedol": "", "asset_class": "Cash", "sector_type": "", "source_url": "fixture"},
            ]
            _write_csv(saved, list(rows[0]), rows)
            return SimpleNamespace(status="succeeded", references=[str(saved)], row_counts={"etf_holding_snapshot": len(rows)}, details={"run_id": run_id})

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            universe = root / "etfs.csv"
            _write_csv(
                universe,
                ["symbol", "issuer_name", "model_layer", "universe_type"],
                [
                    {"symbol": "XLK", "issuer_name": "State Street / SPDR", "model_layer": "layer_02_sector_context", "universe_type": "sector_observation_etf"},
                    {"symbol": "SPY", "issuer_name": "State Street / SPDR", "model_layer": "layer_01_market_regime", "universe_type": "market_state_etf"},
                ],
            )

            try:
                holdings_module._run_feed = fake_run_feed
                rows, receipt = collect_holdings(
                    universe_csv=universe,
                    output_root=root / "out",
                    as_of_date="2026-06-04",
                    model_layers={"layer_02_sector_context"},
                    allow_partial=True,
                )
            finally:
                holdings_module._run_feed = original

        self.assertEqual([(row["etf_symbol"], row["holding_symbol"]) for row in rows], [("XLK", "NVDA")])
        self.assertEqual(receipt["requested_etf_count"], 1)
        self.assertEqual(receipt["selected_holding_row_count"], 1)

    def test_build_pool_uses_configured_realtime_rank_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tradingview = root / "tradingview.csv"
            _write_csv(
                tradingview,
                ["Ticker", "Name", "Sector", "Volume", "Market Cap"],
                [
                    {"Ticker": "NVDA", "Name": "NVIDIA", "Sector": "Technology", "Volume": "100M", "Market Cap": "4T"},
                    {"Ticker": "MSFT", "Name": "Microsoft", "Sector": "Technology", "Volume": "90M", "Market Cap": "3T"},
                ],
            )

            rows, receipt = build_pool(
                tradingview_csvs=[tradingview],
                optionable_symbols_file=None,
                as_of_date="2026-06-04",
                rank_limit=1,
                allow_unknown_optionability=True,
            )

        by_symbol = {row.symbol: row for row in rows}
        self.assertEqual(set(by_symbol), {"MSFT", "NVDA"})
        self.assertTrue(by_symbol["NVDA"].in_recent_week_volume_top300)
        self.assertFalse(by_symbol["MSFT"].in_recent_week_volume_top300)
        self.assertEqual(by_symbol["MSFT"].pool_membership_status, "inactive")
        self.assertEqual(receipt["input_symbol_count"], 2)
        self.assertEqual(receipt["rank_limit"], 1)

    def test_build_historical_candidate_universe_freezes_current_active_pool_and_crypto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pool = root / "equity_total_symbol_pool.csv"
            _write_csv(
                pool,
                [
                    "symbol",
                    "name",
                    "sector",
                    "optionable_underlying_status",
                    "pool_membership_status",
                    "pool_membership_reason",
                    "in_recent_week_volume_top300",
                    "in_market_cap_top300",
                    "volume_rank",
                    "market_cap_rank",
                    "source_refs",
                    "as_of_date",
                ],
                [
                    {"symbol": "NVDA", "name": "NVIDIA", "sector": "Technology", "optionable_underlying_status": "uncertain_verify_before_use", "pool_membership_status": "active", "pool_membership_reason": "active", "in_recent_week_volume_top300": "true", "in_market_cap_top300": "true", "volume_rank": "8", "market_cap_rank": "1", "source_refs": "fixture", "as_of_date": "2026-06-04"},
                    {"symbol": "XYZ", "name": "Inactive", "sector": "", "optionable_underlying_status": "no_listed_options_or_unverified", "pool_membership_status": "inactive", "pool_membership_reason": "inactive", "in_recent_week_volume_top300": "false", "in_market_cap_top300": "false", "volume_rank": "", "market_cap_rank": "", "source_refs": "fixture", "as_of_date": "2026-06-04"},
                ],
            )

            rows, receipt = build_universe(source_pool_csv=pool, freeze_as_of_date="2026-06-04")

        by_symbol = {row.symbol: row for row in rows}
        self.assertEqual(set(by_symbol), {"BTC", "ETH", "NVDA", "SOL"})
        self.assertEqual(by_symbol["NVDA"].replay_candidate_status, "active")
        self.assertEqual(by_symbol["NVDA"].source_pool_as_of_date, "2026-06-04")
        self.assertEqual(by_symbol["NVDA"].asset_class, "us_equity")
        self.assertEqual(by_symbol["NVDA"].layer2_context_symbol, "XLK")
        self.assertEqual(by_symbol["BTC"].asset_class, "crypto_spot")
        self.assertEqual(by_symbol["BTC"].layer2_context_symbol, "BKCH")
        self.assertEqual(receipt["active_candidate_count"], 4)
        self.assertEqual(receipt["asset_class_counts"], {"us_equity": 1, "crypto_spot": 3})
        self.assertIn("not point-in-time historical", receipt["boundary_note"])


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
