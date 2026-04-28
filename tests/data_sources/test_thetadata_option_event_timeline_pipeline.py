import csv
import json
import tempfile
import unittest
from pathlib import Path

from trading_data.data_sources.thetadata_option_event_timeline.pipeline import run
from trading_data.source_availability.http import HttpResult


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
                            "trade_timestamp": "2026-04-24T09:30:02.267",
                            "quote_timestamp": "2026-04-24T09:30:02.260",
                            "price": 1.25,
                            "size": 80,
                            "bid": 1.15,
                            "ask": 1.25,
                            "bid_size": 12,
                            "ask_size": 15,
                            "condition": 134,
                            "sequence": 1,
                        },
                        {
                            "trade_timestamp": "2026-04-24T09:30:10.100",
                            "quote_timestamp": "2026-04-24T09:30:10.050",
                            "price": 1.2,
                            "size": 40,
                            "bid": 1.1,
                            "ask": 1.25,
                            "condition": 130,
                            "sequence": 2,
                        },
                    ],
                }
            ]
        }
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(payload).encode())


class ThetaDataOptionEventTimelinePipelineTests(unittest.TestCase):
    def test_run_saves_event_csv_and_detail_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "thetadata_option_event_timeline_task_test"
            task_key = {
                "task_id": "thetadata_option_event_timeline_task_test",
                "bundle": "thetadata_option_event_timeline",
                "params": {
                    "underlying": "AAPL",
                    "expiration": "2026-05-15",
                    "right": "CALL",
                    "strike": 270,
                    "start_date": "2026-04-24",
                    "end_date": "2026-04-24",
                    "timeframe": "30Min",
                    "thetadata_base_url": "http://127.0.0.1:25503",
                    "current_standard": {
                        "standard_context": {
                            "standard_source": "task_key_current_standard",
                            "standard_id": "opt_evt_std_TEST1234",
                            "generated_at_et": "2026-04-24T09:30:02.500000-04:00",
                        },
                        "trade_at_ask": {
                            "max_price_vs_ask": 0.01,
                            "min_ask_touch_ratio": 0.95,
                        },
                        "opening_activity": {
                            "min_window_volume": 100,
                            "min_volume_percentile_20d_same_time": None,
                        },
                    },
                },
                "output_root": str(output_root),
            }
            result = run(task_key, run_id="thetadata_option_event_timeline_run_test", client=FakeThetaDataClient())

            self.assertEqual(result.status, "succeeded")
            saved_dir = output_root / "runs" / "thetadata_option_event_timeline_run_test" / "saved"
            csv_path = saved_dir / "option_activity_event.csv"
            self.assertTrue(csv_path.exists())
            self.assertFalse((saved_dir / "option_activity_event.csv.tmp").exists())

            with csv_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            event_id = rows[0]["id"]
            self.assertTrue(event_id.startswith("opt_evt_"))
            self.assertNotIn("data_kind", rows[0])
            self.assertIn("AAPL 2026-05-15 270C", rows[0]["headline"])
            self.assertEqual(rows[0]["created_at"], "2026-04-24T09:30:02.267000-04:00")
            self.assertEqual(rows[0]["updated_at"], "2026-04-24T09:30:02.500000-04:00")
            self.assertEqual(rows[0]["symbols"], "AAPL;AAPL 2026-05-15 270C")
            self.assertEqual(rows[0]["summary"], "trade_at_ask;opening_activity")
            self.assertEqual(rows[0]["url"], f"{event_id}.csv")

            detail_path = saved_dir / f"{event_id}.csv"
            self.assertTrue(detail_path.exists())
            self.assertFalse((saved_dir / f"{event_id}.csv.tmp").exists())
            with detail_path.open(newline="") as handle:
                detail = next(csv.DictReader(handle))
            self.assertNotIn("data_kind", detail)
            self.assertEqual(detail["event_id"], event_id)
            self.assertEqual(detail["contract_symbol"], "AAPL 2026-05-15 270C")
            triggered = json.loads(detail["triggered_indicators"])
            self.assertEqual(set(triggered), {"trade_at_ask", "opening_activity"})
            self.assertEqual(triggered["trade_at_ask"]["statistics"]["trade_price"], 1.25)
            self.assertEqual(triggered["opening_activity"]["statistics"]["window_volume"], 120)
            self.assertEqual(json.loads(detail["triggering_trade"])["trade_size"], 80)
            self.assertEqual(json.loads(detail["quote_context"])["ask"], 1.25)
            self.assertEqual(json.loads(detail["source_refs"])["raw_persistence"], "not_persisted_by_default")

            self.assertTrue((output_root / "runs" / "thetadata_option_event_timeline_run_test" / "cleaned" / "option_activity_event.jsonl").exists())
            self.assertFalse((saved_dir / "option_activity_event.jsonl").exists())
            receipt = json.loads((output_root / "completion_receipt.json").read_text())
            self.assertEqual(receipt["bundle"], "thetadata_option_event_timeline")
            self.assertEqual(receipt["runs"][0]["row_counts"]["option_activity_event"], 1)
            self.assertEqual(receipt["runs"][0]["row_counts"]["option_activity_event_detail"], 1)

    def test_requires_current_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "thetadata_option_event_timeline_task_test",
                "bundle": "thetadata_option_event_timeline",
                "params": {
                    "underlying": "AAPL",
                    "expiration": "2026-05-15",
                    "right": "CALL",
                    "strike": 270,
                    "start_date": "2026-04-24",
                    "end_date": "2026-04-24",
                    "timeframe": "30Min",
                },
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run_missing_standard", client=FakeThetaDataClient())
            self.assertEqual(result.status, "failed")
            self.assertIn("current_standard is required", result.details["error"]["message"])


if __name__ == "__main__":
    unittest.main()
