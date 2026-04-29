import csv
import json
import tempfile
import unittest
from pathlib import Path

from data_sources.thetadata_option_primary_tracking.pipeline import run
from source_availability.http import HttpResult


class FakeThetaDataClient:
    def get(self, url, *, params=None, headers=None):
        self.last_url = url
        self.last_params = params or {}
        payload = {
            "response": [
                {
                    "contract": {
                        "symbol": "AAPL",
                        "expiration": "2026-05-15",
                        "right": "CALL",
                        "strike": 270.0,
                    },
                    "data": [
                        {
                            "timestamp": "2026-04-24T09:30:00.000",
                            "open": 0.0,
                            "high": 0.0,
                            "low": 0.0,
                            "close": 0.0,
                            "volume": 0,
                            "count": 0,
                            "vwap": 0.0,
                        },
                        {
                            "timestamp": "2026-04-24T09:30:02.000",
                            "open": 10.0,
                            "high": 10.0,
                            "low": 10.0,
                            "close": 10.0,
                            "volume": 1,
                            "count": 1,
                            "vwap": 10.0,
                        },
                        {
                            "timestamp": "2026-04-24T09:30:30.000",
                            "open": 9.0,
                            "high": 9.2,
                            "low": 8.9,
                            "close": 9.0,
                            "volume": 2,
                            "count": 2,
                            "vwap": 9.3,
                        },
                        {
                            "timestamp": "2026-04-24T09:31:01.000",
                            "open": 8.0,
                            "high": 8.5,
                            "low": 7.9,
                            "close": 8.2,
                            "volume": 3,
                            "count": 3,
                            "vwap": 8.8,
                        },
                    ],
                }
            ]
        }
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(payload).encode())


class ThetaDataOptionPrimaryTrackingPipelineTests(unittest.TestCase):
    def test_run_saves_final_csv_and_skips_zero_volume_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "thetadata_option_primary_tracking_task_test"
            task_key = {
                "task_id": "thetadata_option_primary_tracking_task_test",
                "bundle": "thetadata_option_primary_tracking",
                "params": {
                    "underlying": "AAPL",
                    "expiration": "2026-05-15",
                    "right": "CALL",
                    "strike": 270,
                    "start_date": "2026-04-24",
                    "end_date": "2026-04-24",
                    "timeframe": "1Min",
                    "thetadata_base_url": "http://127.0.0.1:25503",
                },
                "output_root": str(output_root),
            }
            result = run(task_key, run_id="thetadata_option_primary_tracking_run_test", client=FakeThetaDataClient())

            self.assertEqual(result.status, "succeeded")
            saved_path = output_root / "runs" / "thetadata_option_primary_tracking_run_test" / "saved" / "option_bar.csv"
            self.assertTrue(saved_path.exists())
            self.assertFalse((saved_path.parent / "option_bar.csv.tmp").exists())
            self.assertFalse((saved_path.parent / "option_bar.jsonl").exists())

            with saved_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertNotIn("data_kind", rows[0])
            self.assertNotIn("source", rows[0])
            self.assertEqual(rows[0]["underlying"], "AAPL")
            self.assertEqual(rows[0]["expiration"], "2026-05-15")
            self.assertEqual(rows[0]["option_right_type"], "CALL")
            self.assertEqual(rows[0]["strike"], "270.0")
            self.assertEqual(rows[0]["timeframe"], "1Min")
            self.assertEqual(rows[0]["timestamp"], "2026-04-24T09:30:00-04:00")
            self.assertEqual(rows[0]["open"], "10.0")
            self.assertEqual(rows[0]["high"], "10.0")
            self.assertEqual(rows[0]["low"], "8.9")
            self.assertEqual(rows[0]["close"], "9.0")
            self.assertEqual(rows[0]["volume"], "3")
            self.assertEqual(rows[0]["trade_count"], "3")
            self.assertEqual(rows[0]["vwap"], "9.3333333333")
            self.assertEqual(rows[1]["timestamp"], "2026-04-24T09:31:00-04:00")

            cleaned_jsonl = output_root / "runs" / "thetadata_option_primary_tracking_run_test" / "cleaned" / "option_bar.jsonl"
            self.assertTrue(cleaned_jsonl.exists())
            manifest = json.loads((output_root / "runs" / "thetadata_option_primary_tracking_run_test" / "request_manifest.json").read_text())
            self.assertEqual(manifest["raw_persistence"], "not_persisted_by_default")
            self.assertEqual(manifest["params"]["aggregation_timeframe"], "1Min")
            self.assertEqual(manifest["params"]["strike"], "270.000")

            receipt = json.loads((output_root / "completion_receipt.json").read_text())
            self.assertEqual(receipt["bundle"], "thetadata_option_primary_tracking")
            self.assertEqual(receipt["runs"][0]["row_counts"]["option_bar"], 2)
            self.assertEqual(receipt["runs"][0]["row_counts"]["active_option_ohlc_rows_transient"], 3)

    def test_requires_timeframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "thetadata_option_primary_tracking_task_test",
                "bundle": "thetadata_option_primary_tracking",
                "params": {
                    "underlying": "AAPL",
                    "expiration": "2026-05-15",
                    "right": "CALL",
                    "strike": 270,
                    "start_date": "2026-04-24",
                    "end_date": "2026-04-24",
                },
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run_missing_timeframe", client=FakeThetaDataClient())
            self.assertEqual(result.status, "failed")
            self.assertIn("timeframe is required", result.details["error"]["message"])


if __name__ == "__main__":
    unittest.main()
