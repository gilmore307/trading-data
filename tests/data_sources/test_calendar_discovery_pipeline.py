from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from trading_data.data_sources.calendar_discovery.pipeline import parse_ics, run
from trading_data.source_availability.http import HttpResult


class FakeCalendarClient:
    def __init__(self, body: str, content_type: str = "text/calendar"):
        self.body = body
        self.content_type = content_type

    def get(self, url, *, params=None, headers=None):
        return HttpResult(url=url, status=200, headers={"Content-Type": self.content_type}, body=self.body.encode())


class CalendarDiscoveryPipelineTests(unittest.TestCase):
    def test_parse_ics_release_events(self):
        rows = parse_ics(
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:CPI Release\nDTSTART:20240410T083000\nEND:VEVENT\nEND:VCALENDAR\n",
            calendar_source="unit_calendar",
            source_url="https://official.example/calendar.ics",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_name"], "CPI Release")
        self.assertEqual(rows[0]["release_time"], "2024-04-10T08:30:00-04:00")

    def test_run_saves_release_calendar_csv_from_ics(self):
        body = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Employment Situation\nDTSTART:20240503T083000\nEND:VEVENT\nEND:VCALENDAR\n"
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "calendar_discovery_task_test",
                "bundle": "calendar_discovery",
                "params": {"calendar_source": "bls_release_calendar", "url": "https://official.example/bls.ics", "format": "ics"},
                "output_root": str(Path(tmp) / "calendar_discovery_task_test"),
            }
            result = run(task_key, run_id="calendar_discovery_run_test", client=FakeCalendarClient(body))
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "calendar_discovery_run_test" / "saved" / "release_calendar.csv"
            self.assertTrue(saved.exists())
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["calendar_source"], "bls_release_calendar")
            self.assertEqual(row["event_name"], "Employment Situation")
            self.assertEqual(row["release_time"], "2024-05-03T08:30:00-04:00")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["row_counts"]["release_calendar"], 1)

    def test_run_saves_release_calendar_csv_from_json(self):
        body = json.dumps({"events": [{"name": "Retail Sales", "release_time": "2024-04-15T08:30:00-04:00"}]})
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "calendar_discovery_task_json",
                "bundle": "calendar_discovery",
                "params": {"calendar_source": "census_release_calendar", "url": "https://official.example/calendar.json"},
                "output_root": str(Path(tmp) / "calendar_discovery_task_json"),
            }
            result = run(task_key, run_id="calendar_discovery_run_json", client=FakeCalendarClient(body, "application/json"))
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["release_calendar"], 1)


if __name__ == "__main__":
    unittest.main()
