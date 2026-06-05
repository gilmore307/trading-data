import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from importlib import import_module

pipeline = import_module("data_feed.09_feed_thetadata_option_selection_snapshot.pipeline")
run = pipeline.run
from feed_availability.http import HttpResult


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


class FakeHistoricalThetaDataClient:
    def get(self, url, *, params=None, headers=None):
        if url.endswith("/history/quote"):
            payload = {
                "response": [
                    {
                        "contract": {
                            "symbol": "AAPL",
                            "expiration": "2016-01-15",
                            "right": "CALL",
                            "strike": 100.0,
                        },
                        "data": [
                            {
                                "timestamp": "2016-01-05T09:30:00",
                                "bid": 1.0,
                                "ask": 1.2,
                                "bid_size": 10,
                                "ask_size": 11,
                            },
                            {
                                "timestamp": "2016-01-05T09:31:00",
                                "bid": 1.1,
                                "ask": 1.3,
                                "bid_size": 12,
                                "ask_size": 13,
                            },
                        ],
                    }
                ]
            }
        elif url.endswith("/history/greeks/eod"):
            payload = {
                "response": [
                    {
                        "contract": {
                            "symbol": "AAPL",
                            "expiration": "2016-01-15",
                            "right": "CALL",
                            "strike": 100.0,
                        },
                        "data": [
                            {
                                "timestamp": "2016-01-05T16:00:00",
                                "implied_vol": 0.32,
                                "iv_error": 0.0,
                                "delta": 0.51,
                                "theta": -0.03,
                                "vega": 0.11,
                                "rho": 0.02,
                                "epsilon": -0.1,
                                "lambda": 4.0,
                                "underlying_price": 101.0,
                                "underlying_timestamp": "2016-01-05T21:00:00",
                            }
                        ],
                    }
                ]
            }
        elif url.endswith("/history/trade"):
            payload = {
                "response": [
                    {
                        "contract": {
                            "symbol": "AAPL",
                            "expiration": "2016-01-15",
                            "right": "CALL",
                            "strike": 100.0,
                        },
                        "data": [
                            {"timestamp": "2016-01-05T09:30:10", "price": 1.1, "size": 2},
                            {"timestamp": "2016-01-05T09:30:40", "price": 1.2, "size": 3},
                            {"timestamp": "2016-01-05T09:31:15", "price": 1.25, "size": 4},
                        ],
                    }
                ]
            }
        else:
            payload = {"response": []}
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(payload).encode())


class CapturingThetaDataClient(FakeThetaDataClient):
    instances = []

    def __init__(self, *, timeout_seconds, retry_policy):
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy
        self.instances.append(self)


class ThetaDataOptionSelectionSnapshotPipelineTests(unittest.TestCase):
    def test_run_saves_final_csv_only_with_snapshot_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "09_feed_thetadata_option_selection_snapshot_task_test"
            task_key = {
                "task_id": "09_feed_thetadata_option_selection_snapshot_task_test",
                "feed": "09_feed_thetadata_option_selection_snapshot",
                "params": {
                    "underlying": "AAPL",
                    "snapshot_time": "2026-04-24T09:30:02.500000-04:00",
                    "historical_mode": False,
                    "thetadata_base_url": "http://127.0.0.1:25503",
                },
                "output_root": str(output_root),
            }
            result = run(task_key, run_id="09_feed_thetadata_option_selection_snapshot_run_test", client=FakeThetaDataClient(), client_is_fixture=True)

            self.assertEqual(result.status, "succeeded")
            saved_path = output_root / "runs" / "09_feed_thetadata_option_selection_snapshot_run_test" / "saved" / "option_chain_snapshot.csv"
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

            manifest = json.loads((output_root / "runs" / "09_feed_thetadata_option_selection_snapshot_run_test" / "request_manifest.json").read_text())
            self.assertEqual(manifest["raw_persistence"], "not_persisted_by_default")
            self.assertEqual(manifest["params"]["historical_mode"], False)
            self.assertEqual(manifest["params"]["max_dte"], "45")
            self.assertEqual(manifest["params"]["strike_range"], "5")
            self.assertEqual(manifest["params"]["option_bucket_policy_ref"], "LAYER_09_OPTION_BUCKET_STRIKE_POLICY")

            receipt = json.loads((output_root / "completion_receipt.json").read_text())
            self.assertEqual(receipt["feed"], "09_feed_thetadata_option_selection_snapshot")
            self.assertEqual(receipt["runs"][0]["row_counts"]["option_chain_snapshot_contracts"], 1)

    def test_requires_explicit_snapshot_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "09_feed_thetadata_option_selection_snapshot_task_test",
                "feed": "09_feed_thetadata_option_selection_snapshot",
                "params": {"underlying": "AAPL"},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run_missing_time", client=FakeThetaDataClient(), client_is_fixture=True)
            self.assertEqual(result.status, "failed")
            self.assertIn("snapshot_time is required", result.details["error"]["message"])

    def test_default_client_uses_bounded_retry_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            CapturingThetaDataClient.instances = []
            output_root = Path(tmp) / "09_feed_thetadata_option_selection_snapshot_task_test"
            task_key = {
                "task_id": "09_feed_thetadata_option_selection_snapshot_task_test",
                "feed": "09_feed_thetadata_option_selection_snapshot",
                "params": {
                    "underlying": "AAPL",
                    "snapshot_time": "2026-04-24T09:30:02.500000-04:00",
                    "historical_mode": False,
                    "thetadata_base_url": "http://127.0.0.1:25503",
                },
                "output_root": str(output_root),
            }
            with patch.object(pipeline, "HttpClient", CapturingThetaDataClient):
                result = run(task_key, run_id="run_default_retry", client_is_fixture=True)

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(len(CapturingThetaDataClient.instances), 1)
            client = CapturingThetaDataClient.instances[0]
            self.assertEqual(client.timeout_seconds, 30)
            self.assertEqual(client.retry_policy.max_attempts, 3)
            self.assertEqual(client.retry_policy.backoff_seconds, 1.0)
            manifest = json.loads((output_root / "runs" / "run_default_retry" / "request_manifest.json").read_text())
            self.assertEqual(manifest["params"]["retry_attempts"], 3)
            self.assertEqual(manifest["params"]["retry_backoff_seconds"], 1.0)

    def test_historical_window_keeps_each_minute_and_trade_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "09_feed_thetadata_option_selection_snapshot_task_test"
            task_key = {
                "task_id": "09_feed_thetadata_option_selection_snapshot_task_test",
                "feed": "09_feed_thetadata_option_selection_snapshot",
                "params": {
                    "underlying": "AAPL",
                    "snapshot_time": "2016-01-05T09:30:00-05:00",
                    "window_start": "2016-01-05T09:30:00-05:00",
                    "window_end": "2016-01-05T09:31:59.999000-05:00",
                    "historical_mode": True,
                    "thetadata_base_url": "http://127.0.0.1:25503",
                },
                "output_root": str(output_root),
            }
            result = run(
                task_key,
                run_id="09_feed_thetadata_option_selection_snapshot_window_test",
                client=FakeHistoricalThetaDataClient(),
                client_is_fixture=True,
            )

            self.assertEqual(result.status, "succeeded")
            saved_path = output_root / "runs" / "09_feed_thetadata_option_selection_snapshot_window_test" / "saved" / "option_chain_snapshot.csv"
            with saved_path.open(newline="") as handle:
                snapshot = next(csv.DictReader(handle))
            contracts = json.loads(snapshot["contracts"])

            self.assertEqual(snapshot["contract_count"], "2")
            self.assertEqual([contract["snapshot_time"] for contract in contracts], [
                "2016-01-05T09:30:00-05:00",
                "2016-01-05T09:31:00-05:00",
            ])
            self.assertEqual(contracts[0]["quote"]["mid"], 1.1)
            self.assertEqual(contracts[0]["trade_summary"]["bar_trade_count"], 2)
            self.assertEqual(contracts[0]["trade_summary"]["bar_volume"], 5)
            self.assertEqual(contracts[1]["trade_summary"]["bar_close"], 1.25)

            manifest = json.loads((output_root / "runs" / "09_feed_thetadata_option_selection_snapshot_window_test" / "request_manifest.json").read_text())
            self.assertEqual(manifest["window_start"], "2016-01-05T09:30:00-05:00")
            self.assertEqual(manifest["window_end"], "2016-01-05T09:31:59.999000-05:00")


if __name__ == "__main__":
    unittest.main()
