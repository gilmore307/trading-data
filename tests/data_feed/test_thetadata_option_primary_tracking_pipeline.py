import json
import tempfile
import unittest
from pathlib import Path

from importlib import import_module
from tests.data_feed.fake_sql import FakeSqlWriter

run = import_module("data_feed.10_feed_thetadata_option_primary_tracking.pipeline").run
from feed_availability.http import HttpResult


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


class FakeThetaDataFrame:
    def __init__(self, rows):
        self._rows = rows

    def to_dicts(self):
        return self._rows


class FakeThetaDataPythonClient:
    def __init__(self):
        self.calls = []

    def option_history_ohlc(self, **kwargs):
        self.calls.append(kwargs)
        return FakeThetaDataFrame(
            [
                {
                    "symbol": kwargs["symbol"],
                    "expiration": kwargs["expiration"].isoformat(),
                    "right": kwargs["right"],
                    "strike": 270.0,
                    "timestamp": "2026-04-24T09:30:00.000",
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 1,
                    "count": 1,
                    "vwap": 10.0,
                },
                {
                    "symbol": kwargs["symbol"],
                    "expiration": kwargs["expiration"].isoformat(),
                    "right": kwargs["right"],
                    "strike": 270.0,
                    "timestamp": "2026-04-24T09:31:00.000",
                    "open": 10.5,
                    "high": 10.5,
                    "low": 10.2,
                    "close": 10.3,
                    "volume": 2,
                    "count": 2,
                    "vwap": 10.3,
                },
            ]
        )


class ThetaDataOptionPrimaryTrackingPipelineTests(unittest.TestCase):
    def test_run_saves_final_csv_and_skips_zero_volume_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "10_feed_thetadata_option_primary_tracking_task_test"
            task_key = {
                "task_id": "10_feed_thetadata_option_primary_tracking_task_test",
                "feed": "10_feed_thetadata_option_primary_tracking",
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
            writer = FakeSqlWriter()
            result = run(task_key, run_id="10_feed_thetadata_option_primary_tracking_run_test", client=FakeThetaDataClient(), client_is_fixture=True, sql_writer=writer)

            self.assertEqual(result.status, "succeeded")
            saved_path = output_root / "runs" / "10_feed_thetadata_option_primary_tracking_run_test" / "saved" / "option_bar.csv"
            self.assertFalse(saved_path.exists())
            self.assertFalse((saved_path.parent / "option_bar.csv.tmp").exists())
            self.assertFalse((saved_path.parent / "option_bar.jsonl").exists())

            rows = writer.rows_for("feed_10_option_bar")
            self.assertEqual(len(rows), 2)
            self.assertNotIn("data_kind", rows[0])
            self.assertNotIn("source", rows[0])
            self.assertEqual(rows[0]["underlying"], "AAPL")
            self.assertEqual(rows[0]["expiration"], "2026-05-15")
            self.assertEqual(rows[0]["option_right_type"], "CALL")
            self.assertEqual(rows[0]["strike"], 270.0)
            self.assertEqual(rows[0]["timeframe"], "1Min")
            self.assertEqual(rows[0]["timestamp"], "2026-04-24T09:30:00-04:00")
            self.assertEqual(rows[0]["bar_open"], 10.0)
            self.assertEqual(rows[0]["bar_high"], 10.0)
            self.assertEqual(rows[0]["bar_low"], 8.9)
            self.assertEqual(rows[0]["bar_close"], 9.0)
            self.assertEqual(rows[0]["bar_volume"], 3)
            self.assertEqual(rows[0]["bar_trade_count"], 3)
            self.assertEqual(rows[0]["bar_vwap"], 9.3333333333)
            self.assertEqual(rows[1]["timestamp"], "2026-04-24T09:31:00-04:00")

            cleaned_jsonl = output_root / "runs" / "10_feed_thetadata_option_primary_tracking_run_test" / "cleaned" / "option_bar.jsonl"
            self.assertFalse(cleaned_jsonl.exists())
            manifest = json.loads((output_root / "runs" / "10_feed_thetadata_option_primary_tracking_run_test" / "request_manifest.json").read_text())
            self.assertEqual(manifest["raw_persistence"], "not_persisted_by_default")
            self.assertEqual(manifest["params"]["aggregation_timeframe"], "1Min")
            self.assertEqual(manifest["params"]["interval"], "1m")
            self.assertEqual(manifest["params"]["strike"], "270.000")
            self.assertEqual(manifest["params"]["thetadata_transport"], "terminal_rest")

            receipt = json.loads((output_root / "completion_receipt.json").read_text())
            self.assertEqual(receipt["feed"], "10_feed_thetadata_option_primary_tracking")
            self.assertEqual(receipt["runs"][0]["row_counts"]["option_bar"], 2)
            self.assertEqual(receipt["runs"][0]["row_counts"]["active_option_ohlc_rows_transient"], 3)

    def test_default_transport_uses_python_library_exact_ohlc(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "10_feed_thetadata_option_primary_tracking_task_test"
            task_key = {
                "task_id": "10_feed_thetadata_option_primary_tracking_task_test",
                "feed": "10_feed_thetadata_option_primary_tracking",
                "manager_controls": {
                    "allow_live_provider_calls": True,
                    "autonomous_historical_provider_acquisition": True,
                    "allowed_providers": ["thetadata"],
                    "allowed_endpoint_families": ["option_primary_tracking"],
                    "max_symbols": 1,
                    "max_time_window": "1d",
                },
                "params": {
                    "underlying": "AAPL",
                    "expiration": "2026-05-15",
                    "right": "CALL",
                    "strike": 270,
                    "start_date": "2026-04-24",
                    "end_date": "2026-04-24",
                    "timeframe": "1Min",
                },
                "output_root": str(output_root),
            }
            writer = FakeSqlWriter()
            client = FakeThetaDataPythonClient()
            result = run(task_key, run_id="run_python_library", theta_client=client, sql_writer=writer)

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(client.calls[0]["right"], "C")
            self.assertEqual(client.calls[0]["strike"], "270")
            self.assertEqual(client.calls[0]["interval"], "1m")
            self.assertEqual(client.calls[0]["start_time"], "09:30:00.000")
            self.assertEqual(client.calls[0]["end_time"], "16:00:00.000")
            rows = writer.rows_for("feed_10_option_bar")
            self.assertEqual(len(rows), 2)
            manifest = json.loads((output_root / "runs" / "run_python_library" / "request_manifest.json").read_text())
            self.assertEqual(manifest["params"]["thetadata_transport"], "python_library")
            self.assertEqual(manifest["request"]["transport"], "python_library")

    def test_requires_timeframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "10_feed_thetadata_option_primary_tracking_task_test",
                "feed": "10_feed_thetadata_option_primary_tracking",
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
            result = run(task_key, run_id="run_missing_timeframe", client=FakeThetaDataClient(), client_is_fixture=True)
            self.assertEqual(result.status, "failed")
            self.assertIn("timeframe is required", result.details["error"]["message"])


if __name__ == "__main__":
    unittest.main()
