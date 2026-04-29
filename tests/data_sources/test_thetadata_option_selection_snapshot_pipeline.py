import csv
import json
import tempfile
import unittest
from pathlib import Path

from importlib import import_module

run = import_module("data_sources.09_source_thetadata_option_selection_snapshot.pipeline").run
from source_availability.http import HttpResult


class FakeThetaDataClient:
    def get(self, url, *, params=None, headers=None):
        self.last_params = params or {}
        if url.endswith("/snapshot/quote"):
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
                                "timestamp": "2026-04-24T09:30:02.260",
                                "bid": 1.15,
                                "ask": 1.25,
                                "bid_size": 12,
                                "ask_size": 15,
                                "bid_exchange": 7,
                                "ask_exchange": 7,
                                "bid_condition": 50,
                                "ask_condition": 50,
                            }
                        ],
                    }
                ]
            }
        elif url.endswith("/snapshot/greeks/implied_volatility"):
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
                                "timestamp": "2026-04-24T09:30:02.260",
                                "implied_vol": 0.64,
                                "iv_error": 0.0,
                                "underlying_price": 271.95,
                                "underlying_timestamp": "2026-04-24T13:30:02.260",
                            }
                        ],
                    }
                ]
            }
        elif url.endswith("/snapshot/greeks/first_order"):
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
                                "timestamp": "2026-04-24T09:30:02.260",
                                "delta": 0.52,
                                "theta": -0.11,
                                "vega": 18.2,
                                "rho": 4.3,
                                "epsilon": -10.5,
                                "lambda": 14.1,
                                "underlying_price": 271.95,
                                "underlying_timestamp": "2026-04-24T13:30:02.260",
                            }
                        ],
                    }
                ]
            }
        else:
            payload = {"response": []}
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(payload).encode())


class ThetaDataOptionSelectionSnapshotPipelineTests(unittest.TestCase):
    def test_run_saves_final_csv_only_with_snapshot_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "09_source_thetadata_option_selection_snapshot_task_test"
            task_key = {
                "task_id": "09_source_thetadata_option_selection_snapshot_task_test",
                "bundle": "09_source_thetadata_option_selection_snapshot",
                "params": {
                    "underlying": "AAPL",
                    "snapshot_time": "2026-04-24T09:30:02.500000-04:00",
                    "thetadata_base_url": "http://127.0.0.1:25503",
                },
                "output_root": str(output_root),
            }
            result = run(task_key, run_id="09_source_thetadata_option_selection_snapshot_run_test", client=FakeThetaDataClient())

            self.assertEqual(result.status, "succeeded")
            saved_path = output_root / "runs" / "09_source_thetadata_option_selection_snapshot_run_test" / "saved" / "option_chain_snapshot.csv"
            self.assertTrue(saved_path.exists())
            self.assertFalse((saved_path.parent / "option_chain_snapshot.csv.tmp").exists())
            self.assertFalse((saved_path.parent / "option_chain_snapshot.jsonl").exists())

            with saved_path.open(newline="") as handle:
                snapshot = next(csv.DictReader(handle))
            self.assertNotIn("data_kind", snapshot)
            self.assertNotIn("source", snapshot)
            self.assertEqual(snapshot["underlying"], "AAPL")
            self.assertEqual(snapshot["snapshot_time"], "2026-04-24T09:30:02.500000-04:00")
            self.assertEqual(snapshot["contract_count"], "1")

            contract = json.loads(snapshot["contracts"])[0]
            self.assertEqual(contract["option_right_type"], "CALL")
            self.assertNotIn("timestamp", contract["quote"])
            self.assertNotIn("timestamp", contract["iv"])
            self.assertNotIn("timestamp", contract["greeks"])
            self.assertEqual(contract["quote"]["mid"], 1.2)
            self.assertEqual(contract["quote"]["spread"], 0.10000000000000009)
            self.assertEqual(contract["iv"]["implied_vol"], 0.64)
            self.assertEqual(contract["greeks"]["delta"], 0.52)
            self.assertEqual(
                contract["underlying_context"]["underlying_timestamp"],
                "2026-04-24T09:30:02.260000-04:00",
            )
            self.assertEqual(contract["derived"]["days_to_expiration"], 21)

            manifest = json.loads((output_root / "runs" / "09_source_thetadata_option_selection_snapshot_run_test" / "request_manifest.json").read_text())
            self.assertEqual(manifest["raw_persistence"], "not_persisted_by_default")
            self.assertEqual(manifest["params"]["ms_of_day"], "34202500")

            receipt = json.loads((output_root / "completion_receipt.json").read_text())
            self.assertEqual(receipt["bundle"], "09_source_thetadata_option_selection_snapshot")
            self.assertEqual(receipt["runs"][0]["row_counts"]["option_chain_snapshot_contracts"], 1)

    def test_requires_explicit_snapshot_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "09_source_thetadata_option_selection_snapshot_task_test",
                "bundle": "09_source_thetadata_option_selection_snapshot",
                "params": {"underlying": "AAPL"},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run_missing_time", client=FakeThetaDataClient())
            self.assertEqual(result.status, "failed")
            self.assertIn("snapshot_time is required", result.details["error"]["message"])


if __name__ == "__main__":
    unittest.main()
