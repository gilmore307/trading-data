import csv
import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path


class FakeSqlWriter:
    def __init__(self):
        self.calls = []

    def write_rows(self, *, table, columns, rows, key_columns):
        self.calls.append({"table": table, "columns": list(columns), "rows": list(rows), "key_columns": list(key_columns)})
        return {"storage_target_id": "test_postgres", "driver": "postgresql", "schema": "trading_source", "table": table, "qualified_table": f"{table}", "rows_written": len(rows)}


class StockEtfExposurePipelineTests(unittest.TestCase):
    def test_security_selection_bundle_writes_filtered_us_equity_holdings(self):
        with tempfile.TemporaryDirectory() as tmp:
            universe = Path(tmp) / "market_etf_universe.csv"
            universe.write_text(
                "symbol,universe_type,exposure_type,bar_grain,fund_name,issuer_name\n"
                "SMH,sector_observation_etf,industry_chain,1d,VanEck Semiconductor ETF,VanEck\n",
                encoding="utf-8",
            )
            holdings = Path(tmp) / "smh_holdings.csv"
            with holdings.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Ticker", "Name", "Weight", "Shares", "Market Value", "Asset Class", "Sector"])
                writer.writeheader()
                writer.writerows([
                    {"Ticker": "NVDA", "Name": "NVIDIA Corp", "Weight": "20", "Shares": "100", "Market Value": "1000", "Asset Class": "Equity", "Sector": "Information Technology"},
                    {"Ticker": "CASH", "Name": "Cash Collateral", "Weight": "2", "Asset Class": "Cash", "Sector": "Cash"},
                    {"Ticker": "SAP", "Name": "SAP SE", "Weight": "1", "Asset Class": "Equity", "Sector": "Technology"},
                ])
            task_key = {
                "task_id": "02_bundle_security_selection_task_test",
                "bundle": "02_bundle_security_selection",
                "params": {
                    "start": "2026-04-24",
                    "end": "2026-04-25",
                    "market_etf_universe_path": str(universe),
                    "available_time": "2026-04-25T09:30:00-04:00",
                    "holding_source_payloads": {"SMH": {"csv_path": str(holdings), "as_of_date": "2026-04-24"}},
                },
                "output_root": str(Path(tmp) / "task"),
            }
            module = import_module("data_bundles.02_bundle_security_selection.pipeline")
            sql_writer = FakeSqlWriter()
            result = module.run(task_key, run_id="run", sql_writer=sql_writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["bundle_02_security_selection"], 1)
            self.assertEqual(len(sql_writer.calls), 1)
            call = sql_writer.calls[0]
            self.assertEqual(call["table"], "bundle_02_security_selection")
            self.assertEqual(call["key_columns"], ["etf_symbol", "as_of_date", "holding_symbol"])
            self.assertEqual(call["columns"], ["etf_symbol", "issuer_name", "universe_type", "exposure_type", "as_of_date", "available_time", "holding_symbol", "holding_name", "weight", "shares", "market_value", "sector_type"])
            rows = call["rows"]
            self.assertEqual(rows[0]["holding_symbol"], "NVDA")
            self.assertEqual(rows[0]["etf_symbol"], "SMH")
            self.assertEqual(rows[0]["universe_type"], "sector_observation_etf")
            self.assertEqual(rows[0]["exposure_type"], "industry_chain")
            self.assertEqual(rows[0]["available_time"], "2026-04-25T09:30:00-04:00")
            self.assertNotIn("run_id", rows[0])
            self.assertNotIn("task_id", rows[0])
            self.assertNotIn("created_at", rows[0])
            self.assertNotIn("cusip", rows[0])
            self.assertNotIn("sedol", rows[0])
            self.assertNotIn("asset_class", rows[0])
            self.assertNotIn("source_url", rows[0])
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["runs"][0]["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
