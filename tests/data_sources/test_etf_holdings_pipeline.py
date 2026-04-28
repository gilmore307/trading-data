import csv
import json
import tempfile
import unittest
from pathlib import Path

from trading_data.data_sources.etf_holdings.pipeline import run


class EtfHoldingsPipelineTests(unittest.TestCase):
    def test_parse_issuer_csv_snapshot(self):
        csv_text = """Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Shares,CUSIP
NVDA,NVIDIA Corp,Information Technology,Equity,"$100,000",18.53%,1234,67066G104
AAPL,Apple Inc,Information Technology,Equity,"$90,000",15.85%,1000,037833100
"""
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "etf_holdings_task_test",
                "bundle": "etf_holdings",
                "params": {
                    "etf_symbol": "VGT",
                    "issuer_name": "vanguard",
                    "as_of_date": "2026-04-24",
                    "source_url": "https://investor.vanguard.com/investment-products/etfs/profile/vgt",
                    "csv_text": csv_text,
                },
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["etf_holding_snapshot"], 2)
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "etf_holding_snapshot.csv"
            with saved.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["etf_symbol"], "VGT")
            self.assertEqual(rows[0]["holding_symbol"], "NVDA")
            self.assertEqual(rows[0]["weight"], "18.53")
            self.assertEqual(rows[0]["market_value"], "100000")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["status"], "succeeded")

    def test_parse_html_holdings_table(self):
        html = """
        <table>
          <tr><th>Ticker</th><th>Holdings</th><th>CUSIP</th><th>SEDOL</th><th>% of fund</th><th>Shares</th><th>Market value</th></tr>
          <tr><td>NVDA</td><td>NVIDIA Corp.</td><td>67066G104</td><td>2379504</td><td>18.53 %</td><td>129,246,346</td><td>$22,540,562,742</td></tr>
        </table>
        """
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "etf_holdings_html_test",
                "bundle": "etf_holdings",
                "params": {"etf_symbol": "VGT", "issuer_name": "vanguard", "as_of_date": "2026-04-24", "html": html},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "etf_holding_snapshot.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["holding_name"], "NVIDIA Corp.")
            self.assertEqual(row["sedol"], "2379504")
            self.assertEqual(row["shares"], "129246346")


if __name__ == "__main__":
    unittest.main()
