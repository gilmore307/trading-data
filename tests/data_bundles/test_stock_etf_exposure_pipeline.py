import csv
import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path


class StockEtfExposurePipelineTests(unittest.TestCase):
    def test_security_selection_bundle_derives_stock_exposure_from_holdings(self):
        with tempfile.TemporaryDirectory() as tmp:
            holdings = Path(tmp) / "etf_holding_snapshot.csv"
            with holdings.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["etf_ticker", "issuer", "as_of_date", "holding_ticker", "holding_name", "weight", "shares", "market_value", "cusip", "sedol", "asset_class", "sector_type", "source_url"])
                writer.writeheader()
                writer.writerows([
                    {"etf_ticker": "SMH", "issuer": "vaneck", "as_of_date": "2026-04-24", "holding_ticker": "NVDA", "holding_name": "NVIDIA Corp", "weight": "20", "sector_type": "Information Technology"},
                    {"etf_ticker": "SOXX", "issuer": "ishares", "as_of_date": "2026-04-24", "holding_ticker": "NVDA", "holding_name": "NVIDIA Corp", "weight": "10", "sector_type": "Information Technology"},
                    {"etf_ticker": "XLK", "issuer": "spdr", "as_of_date": "2026-04-24", "holding_ticker": "AAPL", "holding_name": "Apple Inc", "weight": "15", "sector_type": "Information Technology"},
                ])
            equity_bars = Path(tmp) / "equity_bar.csv"
            equity_bars.write_text("symbol,timestamp,close\nNVDA,2026-04-24T16:00:00-04:00,100\n", encoding="utf-8")
            task_key = {
                "task_id": "02_security_selection_model_inputs_task_test",
                "bundle": "02_security_selection_model_inputs",
                "params": {
                    "as_of": "2026-04-25T09:30:00-04:00",
                    "input_paths": {"equity_bars": str(equity_bars)},
                    "stock_etf_exposure": {
                        "holdings_csv_paths": [str(holdings)],
                        "available_time": "2026-04-25T09:30:00-04:00",
                        "etf_scores": {
                            "SMH": {"sector_score": 0.9, "theme_score": 0.8, "exposure_tags": ["semiconductor", "AI"]},
                            "SOXX": {"sector_score": 0.7, "theme_score": 0.6, "exposure_tags": "semiconductor"},
                            "XLK": {"sector_score": 0.5, "theme_score": 0.4, "exposure_tags": "large_cap_growth"},
                        },
                    },
                },
                "output_root": str(Path(tmp) / "task"),
            }
            module = import_module("trading_data.data_bundles.02_security_selection_model_inputs.pipeline")
            result = module.run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            self.assertGreaterEqual(result.row_counts["02_security_selection_model_inputs"], 2)
            exposure = Path(task_key["output_root"]) / "runs" / "run" / "derived" / "stock_etf_exposure" / "saved" / "stock_etf_exposure.csv"
            with exposure.open(newline="", encoding="utf-8") as handle:
                rows = {row["symbol"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["NVDA"]["exposed_etfs"], "SMH;SOXX")
            self.assertEqual(rows["NVDA"]["top_exposure_etf"], "SMH")
            self.assertEqual(rows["NVDA"]["total_etf_exposure_score"], "0.3")
            self.assertEqual(rows["NVDA"]["weighted_sector_score"], "0.25")
            self.assertIn("semiconductor", rows["NVDA"]["exposure_tags"])
            manifest = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "02_security_selection_model_inputs.csv"
            with manifest.open(newline="", encoding="utf-8") as handle:
                manifest_rows = {row["input_role"]: row for row in csv.DictReader(handle)}
            self.assertEqual(manifest_rows["stock_etf_exposure"]["path"], str(exposure))
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["runs"][0]["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
