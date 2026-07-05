import csv
import json
import tempfile
import unittest
from pathlib import Path

from data_runtime.calendar_observation import (
    build_headline_index_calendar_observations,
    build_market_session_observations,
    build_option_expiry_observations,
    index_calendar_observations,
    index_calendar_observations_from_sql_inputs,
    official_exchange_calendar_observations,
    official_exchange_calendar_observations_from_sql_inputs,
    release_calendar_observations,
    release_calendar_observations_from_sql_inputs,
    trading_economics_observations,
    write_observations,
)


class FakeSqlReader:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.calls = []

    def read_rows(self, *, table, columns, where_equals=None, where_in=None, time_column=None, start=None, end=None, order_by=None):
        self.calls.append({"table": table, "columns": columns, "where_equals": where_equals, "where_in": where_in, "time_column": time_column, "start": start, "end": end, "order_by": order_by})
        return [{column: row.get(column) for column in columns} for row in self.rows_by_table.get(table, [])]


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

    def test_maps_official_exchange_calendar_artifact(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "official_exchange_calendar.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["venue", "calendar_date", "session_status", "open_time", "close_time", "holiday_name", "source_ref"])
                writer.writeheader()
                writer.writerow(
                    {
                        "venue": "NYSE",
                        "calendar_date": "2026-11-27",
                        "session_status": "early_close",
                        "open_time": "2026-11-27T09:30:00-05:00",
                        "close_time": "2026-11-27T13:00:00-05:00",
                        "holiday_name": "Day after Thanksgiving",
                        "source_ref": "https://www.nyse.com/markets/hours-calendars",
                    }
                )
            rows = official_exchange_calendar_observations([path])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].observation_type, "official_exchange_early_close")
            self.assertEqual(rows[0].certainty_status, "confirmed")
            self.assertEqual(rows[0].venue, "NYSE")

    def test_maps_official_exchange_calendar_sql_rows(self):
        reader = FakeSqlReader(
            {
                "feed_12_official_exchange_calendar": [
                    {
                        "venue": "NYSE",
                        "calendar_date": "2026-11-27",
                        "session_status": "early_close",
                        "open_time": "2026-11-27T09:30:00-05:00",
                        "close_time": "2026-11-27T13:00:00-05:00",
                        "holiday_name": "Day after Thanksgiving",
                        "source_ref": "https://www.nyse.com/markets/hours-calendars",
                    }
                ]
            }
        )
        rows = official_exchange_calendar_observations_from_sql_inputs([{}], sql_reader=reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].observation_type, "official_exchange_early_close")
        self.assertEqual(rows[0].venue, "NYSE")
        self.assertEqual(reader.calls[0]["table"], "feed_12_official_exchange_calendar")

    def test_builds_headline_index_schedule_without_djia_shells(self):
        rows = build_headline_index_calendar_observations("2026-12-01", "2026-12-31")
        by_symbol = {row.symbol for row in rows}
        by_type = {row.observation_type for row in rows}
        self.assertIn("NDX", by_symbol)
        self.assertIn("SPX", by_symbol)
        self.assertNotIn("DJIA", by_symbol)
        self.assertIn("index_reconstitution_window", by_type)
        self.assertIn("index_rebalance_window", by_type)

    def test_maps_index_calendar_announcements_and_rejects_etf_sources(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "index_calendar.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["calendar_source", "index_symbol", "event_type", "event_name", "announcement_time", "effective_time", "source_ref"])
                writer.writeheader()
                writer.writerow(
                    {
                        "calendar_source": "sp_dow_jones_indices_announcement",
                        "index_symbol": "DJIA",
                        "event_type": "index_constituent_change",
                        "event_name": "DJIA constituent change",
                        "announcement_time": "2026-05-01T17:15:00-04:00",
                        "effective_time": "2026-05-04T09:30:00-04:00",
                        "source_ref": "https://www.spglobal.com/spdji/",
                    }
                )
                writer.writerow(
                    {
                        "calendar_source": "etf_issuer_page",
                        "index_symbol": "QQQ",
                        "event_type": "index_constituent_change",
                        "event_name": "ETF issuer row must not become index calendar",
                        "announcement_time": "2026-05-01T17:15:00-04:00",
                        "effective_time": "2026-05-04T09:30:00-04:00",
                        "source_ref": "https://example.invalid/qqq",
                    }
                )
            rows = index_calendar_observations([path])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].symbol, "DJIA")
            self.assertEqual(rows[0].source_priority, "official_index_announcement")
            self.assertEqual(rows[0].result_status, "membership_result_available")

    def test_maps_index_calendar_sql_rows(self):
        reader = FakeSqlReader(
            {
                "feed_12_index_calendar": [
                    {
                        "calendar_source": "sp_dow_jones_indices_announcement",
                        "index_symbol": "DJIA",
                        "event_type": "index_constituent_change",
                        "event_name": "DJIA constituent change",
                        "announcement_time": "2026-05-01T17:15:00-04:00",
                        "effective_time": "2026-05-04T09:30:00-04:00",
                        "source_ref": "https://www.spglobal.com/spdji/",
                    }
                ]
            }
        )
        rows = index_calendar_observations_from_sql_inputs([{}], sql_reader=reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].symbol, "DJIA")
        self.assertEqual(rows[0].source_priority, "official_index_announcement")

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

    def test_maps_nasdaq_release_calendar_sql_rows(self):
        reader = FakeSqlReader(
            {
                "feed_12_release_calendar": [
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
                ]
            }
        )
        rows = release_calendar_observations_from_sql_inputs([{}], sql_reader=reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].observation_type, "earnings_calendar")
        self.assertEqual(rows[0].symbol, "AAPL")
        self.assertEqual(rows[0].source_ref, "https://api.nasdaq.com/api/calendar/earnings?date=2026-04-24")

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
            self.assertIn("not_m03_event_state_event_pool", receipt["source_role"])


if __name__ == "__main__":
    unittest.main()
