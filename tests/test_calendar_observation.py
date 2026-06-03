import csv
import json
import tempfile
import unittest
from pathlib import Path

from data_runtime.calendar_observation import (
    build_market_session_observations,
    build_option_expiry_observations,
    release_calendar_observations,
    trading_economics_observations,
    write_observations,
)


class CalendarObservationTests(unittest.TestCase):
    def test_builds_market_session_source_shells(self):
        rows = build_market_session_observations("2026-01-01", "2026-01-03")
        nyse_closed = [row for row in rows if row.venue == "NYSE" and row.calendar_date == "2026-01-01"][0]
        self.assertEqual(nyse_closed.observation_type, "market_session")
        self.assertEqual(nyse_closed.event_phase, "session_window")
        self.assertEqual(nyse_closed.certainty_status, "inferred_rule")

    def test_builds_option_expiry_and_triple_witching_shells(self):
        rows = build_option_expiry_observations("2026-06-15", "2026-06-22")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].calendar_date, "2026-06-19")
        self.assertEqual(rows[0].observation_type, "triple_witching")
        self.assertEqual(rows[0].result_status, "not_result_source")

    def test_maps_nasdaq_release_calendar_to_tentative_earnings_shell(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "release_calendar.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["event_id", "calendar_source", "event_name", "release_time", "event_date", "timezone", "source_url", "raw_summary"])
                writer.writeheader()
                writer.writerow(
                    {
                        "event_id": "cal1",
                        "calendar_source": "nasdaq_earnings_calendar",
                        "event_name": "AAPL earnings release (Apple Inc.)",
                        "release_time": "2026-04-24T08:00:00-04:00",
                        "event_date": "2026-04-24",
                        "timezone": "America/New_York",
                        "source_url": "https://api.nasdaq.com/api/calendar/earnings?date=2026-04-24",
                        "raw_summary": "{}",
                    }
                )
            rows = release_calendar_observations([path])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].observation_type, "earnings_calendar")
            self.assertEqual(rows[0].symbol, "AAPL")
            self.assertEqual(rows[0].certainty_status, "tentative")
            self.assertEqual(rows[0].result_status, "result_fields_not_available")

    def test_maps_trading_economics_rows_to_macro_calendar_shells(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "trading_economics_calendar_event.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "event_time": "2026-06-03T08:15:00-04:00",
                        "country": "United States",
                        "event": "ADP Employment Change",
                        "reference": "MAY",
                        "actual": "122K",
                        "previous": "105K",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rows = trading_economics_observations([path])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].observation_type, "macro_release_calendar")
            self.assertEqual(rows[0].lifecycle_class, "scheduled_recurring_data_release")
            self.assertEqual(rows[0].result_status, "calendar_value_fields_may_be_present")

    def test_writes_calendar_observation_artifacts(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            output_dir = Path(raw_tmp) / "calendar_observation"
            receipt = write_observations(build_option_expiry_observations("2026-06-15", "2026-06-22"), output_dir)
            self.assertEqual(receipt["row_count"], 1)
            self.assertTrue((output_dir / "calendar_observation.csv").exists())
            self.assertTrue((output_dir / "calendar_observation.jsonl").exists())
            self.assertIn("not_layer_10_event_pool", receipt["source_role"])


if __name__ == "__main__":
    unittest.main()
