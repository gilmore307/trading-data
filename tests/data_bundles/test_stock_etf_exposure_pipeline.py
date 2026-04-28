import csv
import json
import tempfile
import unittest
from pathlib import Path

from trading_data.data_bundles.stock_etf_exposure.pipeline import run


class StockEtfExposurePipelineTests(unittest.TestCase):
    def test_builds_point_in_time_stock_exposure_from_holdings(self):
        with tempfile.TemporaryDirectory() as tmp:
            holdings = Path(tmp) / "etf_holding_snapshot.csv"
            with holdings.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["etf_ticker", "issuer", "as_of_date", "holding_ticker", "holding_name", "weight", "shares", "market_value", "cusip", "sedol", "asset_class", "sector", "source_url"])
                writer.writeheader()
                writer.writerows([
                    {"etf_ticker": "SMH", "issuer": "vaneck", "as_of_date": "2026-04-24", "holding_ticker": "NVDA", "holding_name": "NVIDIA Corp", "weight": "20", "sector": "Information Technology"},
                    {"etf_ticker": "SOXX", "issuer": "ishares", "as_of_date": "2026-04-24", "holding_ticker": "NVDA", "holding_name": "NVIDIA Corp", "weight": "10", "sector": "Information Technology"},
                    {"etf_ticker": "XLK", "issuer": "spdr", "as_of_date": "2026-04-24", "holding_ticker": "AAPL", "holding_name": "Apple Inc", "weight": "15", "sector": "Information Technology"},
                ])
            task_key = {
                "task_id": "stock_etf_exposure_task_test",
                "bundle": "stock_etf_exposure",
                "params": {
                    "holdings_csv_paths": [str(holdings)],
                    "available_time_et": "2026-04-25T09:30:00-04:00",
                    "etf_scores": {
                        "SMH": {"sector_score": 0.9, "theme_score": 0.8, "style_tags": ["semiconductor", "AI"]},
                        "SOXX": {"sector_score": 0.7, "theme_score": 0.6, "style_tags": "semiconductor"},
                        "XLK": {"sector_score": 0.5, "theme_score": 0.4, "style_tags": "large_cap_growth"},
                    },
                },
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["stock_etf_exposure"], 2)
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "stock_etf_exposure.csv"
            with saved.open(newline="", encoding="utf-8") as handle:
                rows = {row["symbol"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["NVDA"]["exposed_etfs"], "SMH;SOXX")
            self.assertEqual(rows["NVDA"]["top_exposure_etf"], "SMH")
            self.assertEqual(rows["NVDA"]["total_etf_exposure_score"], "0.3")
            self.assertEqual(rows["NVDA"]["weighted_sector_score"], "0.25")
            self.assertIn("semiconductor", rows["NVDA"]["style_tags"])
            self.assertEqual(rows["NVDA"]["available_time_et"], "2026-04-25T09:30:00-04:00")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["runs"][0]["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
