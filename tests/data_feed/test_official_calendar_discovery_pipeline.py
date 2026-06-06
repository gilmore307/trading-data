from __future__ import annotations

import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path

from feed_availability.http import HttpResult
from tests.data_feed.fake_sql import FakeSqlWriter

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
            writer = FakeSqlWriter()
            result = pipeline.run(task_key, run_id="run", client=FakeCalendarClient(payload), client_is_fixture=True, sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["release_calendar"], 1)
            row = writer.rows_for("feed_12_release_calendar")[0]
            self.assertEqual(row["calendar_source"], "nasdaq_earnings_calendar")
            self.assertEqual(row["event_name"], "AAPL earnings")
            self.assertIn("T16:05:00", row["release_time"])

    def test_nasdaq_earnings_calendar_allows_empty_filtered_result(self):
        payload = {
            "data": {
                "rows": [
                    {"symbol": "MSFT", "name": "Microsoft Corporation", "reportDate": "06/05/2026", "time": "Before Market Open"},
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "12_feed_official_calendar_discovery_task_empty_earnings",
                "feed": "12_feed_official_calendar_discovery",
                "params": {"data_kind": "nasdaq_earnings_calendar", "date": "2026-06-05", "symbols": ["AAPL"]},
                "output_root": str(Path(tmp) / "task"),
            }
            writer = FakeSqlWriter()
            result = pipeline.run(task_key, run_id="run", client=FakeCalendarClient(payload), client_is_fixture=True, sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["release_calendar"], 0)
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            warnings = receipt["runs"][0]["steps"]["clean"]["warnings"]
            self.assertIn("no normalized rows", warnings[0])
            self.assertEqual(writer.calls, [])
            self.assertFalse((Path(task_key["output_root"]) / "runs/run/saved/release_calendar.csv").exists())

    def test_official_exchange_calendar_parses_nyse_holiday_page(self):
        payload = """
        Holidays & Trading Hours
        All NYSE markets observe U.S. holidays as listed below for 2026, 2027, and 2028.
        Holiday 2026 2027 2028
        New Year’s Day Thursday, January 1 Friday, January 1 —*
        Martin Luther King, Jr. Day Monday, January 19 Monday, January 18 Monday, January 17
        Washington's Birthday Monday, February 16 Monday, February 15 Monday, February 21
        Good Friday Friday, April 3 Friday, March 26 Friday, April 14
        Memorial Day Monday, May 25 Monday, May 31 Monday, May 29
        Juneteenth National Independence Day Friday, June 19 Friday, June 18 Monday, June 19
        Independence Day Friday, July 3 Monday, July 5 Tuesday, July 4
        Labor Day Monday, September 7 Monday, September 6 Monday, September 4
        Thanksgiving Day Thursday, November 26 Thursday, November 25 Thursday, November 23
        Christmas Day Friday, December 25 Friday, December 24 Monday, December 25
        Each market will close early at 1:00 p.m. on Friday, November 27, 2026, Friday, November 26, 2027, and Friday, November 24, 2028.
        Each market will close early at 1:00 p.m. on Thursday, December 24, 2026.
        """
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "12_feed_official_calendar_discovery_task_exchange",
                "feed": "12_feed_official_calendar_discovery",
                "params": {
                    "data_kind": "official_exchange_calendar",
                    "source_text": payload,
                    "source_url": "https://www.nyse.com/trade/hours-calendars",
                },
                "output_root": str(Path(tmp) / "task"),
            }
            writer = FakeSqlWriter()
            result = pipeline.run(task_key, run_id="run", client_is_fixture=True, sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            rows = writer.rows_for("feed_12_official_exchange_calendar")
            row_by_key = {(row["venue"], row["calendar_date"], row["session_status"]): row for row in rows}
            self.assertEqual(row_by_key[("NYSE", "2026-01-01", "closed")]["holiday_name"], "New Year’s Day")
            self.assertEqual(row_by_key[("NYSE", "2026-06-19", "closed")]["holiday_name"], "Juneteenth National Independence Day")
            self.assertEqual(row_by_key[("NYSE", "2026-07-03", "closed")]["holiday_name"], "Independence Day")
            self.assertEqual(row_by_key[("NASDAQ", "2026-11-27", "early_close")]["close_time"], "2026-11-27T13:00:00-05:00")
            self.assertEqual(row_by_key[("NYSE", "2026-12-24", "early_close")]["holiday_name"], "Christmas Eve")

    def test_official_exchange_calendar_ignores_observed_suffix_line_prefixes(self):
        payload = """
        Holidays & Trading Hours
        All NYSE markets observe U.S. holidays as listed below for 2026, 2027, and 2028.
        Juneteenth National Independence DayFriday, June 19Friday, June 18 (Juneteenth National
        Independence Day observed)Monday, June 19Independence DayFriday, July 3 (Independence Day observed) Monday, July 5 (Independence Day observed) Tuesday, July 4**
        """
        fetched = pipeline.FetchedCalendarPayload(
            "official_exchange_calendar",
            payload,
            "https://www.nyse.com/trade/hours-calendars",
            200,
            "2026-06-05T00:00:00Z",
            "text",
            {},
        )
        rows = pipeline.normalize_rows(fetched, params={})
        row_by_key = {(row["venue"], row["calendar_date"], row["session_status"]): row for row in rows}
        self.assertEqual(row_by_key[("NYSE", "2026-06-19", "closed")]["holiday_name"], "Juneteenth National Independence Day")
        self.assertEqual(row_by_key[("NYSE", "2026-07-03", "closed")]["holiday_name"], "Independence Day")

    def test_official_exchange_calendar_parses_nyse_html_table_cells(self):
        payload = """
        <title>Holidays &amp; Trading Hours</title>
        <h4>All NYSE markets observe U.S. holidays as listed below for 2026, 2027, and 2028.</h4>
        <table>
          <thead><tr><th>Holiday</th><th>2026</th><th>2027</th><th>2028</th></tr></thead>
          <tbody>
            <tr><th>New Year’s Day</th><td>Thursday, January 1</td><td>Friday, January 1</td><td>—*</td></tr>
            <tr><th>Martin Luther King, Jr. Day</th><td>Monday, January 19</td><td>Monday, January 18</td><td>Monday, January 17</td></tr>
            <tr><th>Juneteenth National Independence Day</th><td>Friday, June 19</td><td>Friday, June 18 (Juneteenth National Independence Day observed)</td><td>Monday, June 19</td></tr>
            <tr><th>Independence Day</th><td>Friday, July 3 (Independence Day observed)</td><td>Monday, July 5 (Independence Day observed)</td><td>Tuesday, July 4**</td></tr>
          </tbody>
        </table>
        """
        fetched = pipeline.FetchedCalendarPayload(
            "official_exchange_calendar",
            payload,
            "https://www.nyse.com/trade/hours-calendars",
            200,
            "2026-06-05T00:00:00Z",
            "text",
            {},
        )
        rows = pipeline.normalize_rows(fetched, params={})
        row_by_key = {(row["venue"], row["calendar_date"], row["session_status"]): row for row in rows}
        self.assertEqual(row_by_key[("NYSE", "2026-06-19", "closed")]["holiday_name"], "Juneteenth National Independence Day")
        self.assertEqual(row_by_key[("NYSE", "2026-07-03", "closed")]["holiday_name"], "Independence Day")
        self.assertNotIn(("NYSE", "2028-01-01", "closed"), row_by_key)

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
            writer = FakeSqlWriter()
            result = pipeline.run(task_key, run_id="run", client_is_fixture=True, sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["index_calendar"], 1)
            row = writer.rows_for("feed_12_index_calendar")[0]
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
