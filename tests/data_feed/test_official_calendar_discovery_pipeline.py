from __future__ import annotations

import csv
import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path

from feed_availability.http import HttpResult

pipeline = import_module("data_feed.12_feed_official_calendar_discovery.pipeline")


class FakeCalendarClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def get(self, url, *, params=None, headers=None):
        self.requests.append((url, params, headers))
        body = self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode()
        return HttpResult(url=url, status=200, headers={"content-type": "application/json"}, body=body)


class OfficialCalendarDiscoveryPipelineTests(unittest.TestCase):
    def test_nasdaq_earnings_calendar_outputs_release_calendar_artifact(self):
        payload = {
            "data": {
                "rows": [
                    {"symbol": "AAPL", "name": "Apple Inc.", "reportDate": "06/05/2026", "time": "After Market Close"},
                    {"symbol": "MSFT", "name": "Microsoft Corporation", "reportDate": "06/05/2026", "time": "Before Market Open"},
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "12_feed_official_calendar_discovery_task_earnings",
                "feed": "12_feed_official_calendar_discovery",
                "params": {"data_kind": "nasdaq_earnings_calendar", "date": "2026-06-05", "symbols": ["AAPL"]},
                "output_root": str(Path(tmp) / "task"),
            }
            result = pipeline.run(task_key, run_id="run", client=FakeCalendarClient(payload), client_is_fixture=True)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["release_calendar"], 1)
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "release_calendar.csv"
            with saved.open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["calendar_source"], "nasdaq_earnings_calendar")
            self.assertEqual(row["event_name"], "AAPL earnings")
            self.assertIn("T16:05:00", row["release_time"])

    def test_official_index_announcement_outputs_index_calendar_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "12_feed_official_calendar_discovery_task_index",
                "feed": "12_feed_official_calendar_discovery",
                "params": {
                    "data_kind": "official_index_announcement",
                    "calendar_source": "sp_dow_jones_indices_announcement",
                    "index_symbol": "DJIA",
                    "event_type": "index_constituent_change",
                    "event_name": "DJIA constituent change",
                    "announcement_time": "2026-05-01T17:15:00-04:00",
                    "effective_time": "2026-05-04T09:30:00-04:00",
                    "source_text": "S&P Dow Jones Indices announces a Dow Jones Industrial Average constituent change.",
                    "source_url": "https://www.spglobal.com/spdji/en/",
                },
                "output_root": str(Path(tmp) / "task"),
            }
            result = pipeline.run(task_key, run_id="run", client_is_fixture=True)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["index_calendar"], 1)
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "index_calendar.csv"
            with saved.open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["calendar_source"], "sp_dow_jones_indices_announcement")
            self.assertEqual(row["index_symbol"], "DJIA")
            self.assertEqual(row["result_status"], "membership_result_available")
            self.assertTrue(Path(row["source_text_path"]).exists())

    def test_rejects_etf_issuer_as_index_calendar_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "12_feed_official_calendar_discovery_task_bad_index",
                "feed": "12_feed_official_calendar_discovery",
                "params": {
                    "data_kind": "official_index_announcement",
                    "source_provider": "etf_issuer_page",
                    "index_symbol": "QQQ",
                    "event_name": "ETF page must not become index calendar",
                    "source_text": "ETF issuer content",
                    "source_url": "https://example.invalid/qqq",
                },
                "output_root": str(Path(tmp) / "task"),
            }
            result = pipeline.run(task_key, run_id="run", client_is_fixture=True)
            self.assertEqual(result.status, "failed")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["error"]["type"], "OfficialCalendarDiscoveryError")


if __name__ == "__main__":
    unittest.main()

