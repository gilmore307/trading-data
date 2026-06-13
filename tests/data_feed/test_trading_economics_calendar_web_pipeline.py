import csv
import json
import tempfile
import unittest
from pathlib import Path

from importlib import import_module

te_pipeline = import_module("data_feed.07_feed_trading_economics_calendar_web.pipeline")
run = te_pipeline.run


class TradingEconomicsCalendarWebPipelineTests(unittest.TestCase):
    def test_parse_sanitized_calendar_html(self):
        html = """
        <table>
          <tr><th>Date</th><th>Country</th><th>Event</th><th>Category</th><th>Reference</th><th>Actual</th><th>Previous</th><th>Consensus</th><th>Forecast</th><th>Revised</th></tr>
          <tr><td>2026-04-03 08:30</td><td>United States</td><td>Non Farm Payrolls</td><td>Labour</td><td>Mar</td><td>228K</td><td>117K</td><td>135K</td><td>140K</td><td></td></tr>
        </table>
        """
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "te_calendar_task_test",
                "feed": "07_feed_trading_economics_calendar_web",
                "params": {"html": html, "start_date": "2026-04-01", "end_date": "2026-04-30", "importance": "3"},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["trading_economics_calendar_event"], 1)
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "trading_economics_calendar_event.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["event"], "Non Farm Payrolls")
            self.assertEqual(row["actual"], "228K")
            self.assertEqual(row["consensus"], "135K")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["status"], "succeeded")

    def test_parse_visible_calendar_page_rows(self):
        html = """
        <table id="calendar">
          <thead><tr><th colspan='3'>Friday January 08 2016</th><th>Actual</th><th>Previous</th><th>Consensus</th><th>Forecast</th></tr></thead>
          <tr data-url="/united-states/non-farm-payrolls" data-id="123" data-country="united states" data-category="non farm payrolls" data-event="non farm payrolls">
            <td class=' 2016-01-08'><span class="event-38 calendar-date-3">08:30 AM</span></td>
            <td class="calendar-item"><table><tr><td><div title="United States"></div></td><td class="calendar-iso">US</td></tr></table></td>
            <td><a class='calendar-event' href='/united-states/non-farm-payrolls'>Non Farm Payrolls</a> <span class="calendar-reference">DEC</span></td>
            <td><a><span id='actual'>292K</span></a></td>
            <td><span id='previous'>252K</span><span id='revised'>®</span></td>
            <td><span id='consensus'>200K</span></td>
            <td><span id='forecast'>205K</span></td>
          </tr>
        </table>
        """
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "te_calendar_page_row_test",
                "feed": "07_feed_trading_economics_calendar_web",
                "params": {"html": html, "start_date": "2016-01-01", "end_date": "2016-02-01", "importance": "3"},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "trading_economics_calendar_event.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["event_time"], "2016-01-08T08:30:00-05:00")
            self.assertEqual(row["country"], "United States")
            self.assertEqual(row["event"], "Non Farm Payrolls")
            self.assertEqual(row["source_event_type"], "non farm payrolls")
            self.assertEqual(row["reference"], "DEC")
            self.assertEqual(row["actual"], "292K")
            self.assertEqual(row["previous"], "252K")
            self.assertEqual(row["consensus"], "200K")
            self.assertEqual(row["te_forecast"], "205K")

    def test_recent_mode_uses_new_york_timezone_cookie_without_auth_cookie(self):
        params = {"date_range_mode": "recent", "use_authenticated_cookies": False, "start_date": "2026-05-18", "end_date": "2026-06-12"}
        cookie_header = te_pipeline._cookie_header(params, cookie_jar=Path("/tmp/no-such-te-cookie-file"))
        self.assertEqual(cookie_header, "cal-timezone-offset=-240")

    def test_recent_monthly_backfill_bucketed_output_writes_event_month_dirs(self):
        html = """
        <table>
          <tr><th>Date</th><th>Country</th><th>Event</th><th>Category</th><th>Reference</th><th>Actual</th><th>Previous</th><th>Consensus</th><th>Forecast</th><th>Revised</th></tr>
          <tr><td>2026-05-29 08:30</td><td>United States</td><td>PCE Price Index</td><td>Inflation</td><td>Apr</td><td>2.1%</td><td>2.2%</td><td>2.1%</td><td>2.1%</td><td></td></tr>
          <tr><td>2026-06-05 08:30</td><td>United States</td><td>Non Farm Payrolls</td><td>Labour</td><td>May</td><td></td><td>115K</td><td>130K</td><td>125K</td><td></td></tr>
        </table>
        """
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "monthly_backfill" / "trading_economics_calendar_web"
            task_key = {
                "task_id": "te_calendar_recent_bucket_test",
                "feed": "07_feed_trading_economics_calendar_web",
                "params": {
                    "html": html,
                    "start_date": "2026-05-26",
                    "end_date": "2026-07-01",
                    "importance": "3",
                    "date_range_mode": "recent",
                    "monthly_backfill_bucketed_output": True,
                },
                "output_root": str(output_root),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            may_saved = output_root / "2026-05" / "runs" / "run" / "saved" / "trading_economics_calendar_event.csv"
            june_saved = output_root / "2026-06" / "runs" / "run" / "saved" / "trading_economics_calendar_event.csv"
            self.assertTrue(may_saved.exists())
            self.assertTrue(june_saved.exists())
            with may_saved.open(newline="", encoding="utf-8") as handle:
                self.assertEqual([row["event"] for row in csv.DictReader(handle)], ["PCE Price Index"])
            with june_saved.open(newline="", encoding="utf-8") as handle:
                self.assertEqual([row["event"] for row in csv.DictReader(handle)], ["Non Farm Payrolls"])
            self.assertTrue((output_root / "2026-05" / "completion_receipt.json").exists())
            self.assertTrue((output_root / "_manifests" / "recent_refresh_completion_receipt.json").exists())

    def test_recent_monthly_backfill_skips_when_rows_are_unchanged(self):
        html = """
        <table>
          <tr><th>Date</th><th>Country</th><th>Event</th><th>Category</th><th>Reference</th><th>Actual</th><th>Previous</th><th>Consensus</th><th>Forecast</th><th>Revised</th></tr>
          <tr><td>2026-06-05 08:30</td><td>United States</td><td>Non Farm Payrolls</td><td>Labour</td><td>May</td><td></td><td>115K</td><td>130K</td><td>125K</td><td></td></tr>
        </table>
        """
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "monthly_backfill" / "trading_economics_calendar_web"
            task_key = {
                "task_id": "te_calendar_recent_bucket_no_change_test",
                "feed": "07_feed_trading_economics_calendar_web",
                "params": {
                    "html": html,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-30",
                    "importance": "3",
                    "date_range_mode": "recent",
                    "monthly_backfill_bucketed_output": True,
                },
                "output_root": str(output_root),
            }

            first = run(task_key, run_id="run1")
            second = run(task_key, run_id="run2")

            self.assertEqual(first.status, "succeeded")
            self.assertEqual(second.status, "skipped_no_new_or_changed_rows")
            self.assertFalse((output_root / "2026-06" / "runs" / "run2").exists())
            self.assertFalse((output_root / "_manifests" / "recent_refresh_runs" / "run2").exists())

    def test_changed_release_value_writes_new_monthly_bucket(self):
        before = """
        <table>
          <tr><th>Date</th><th>Country</th><th>Event</th><th>Category</th><th>Reference</th><th>Actual</th><th>Previous</th><th>Consensus</th><th>Forecast</th><th>Revised</th></tr>
          <tr><td>2026-06-05 08:30</td><td>United States</td><td>Non Farm Payrolls</td><td>Labour</td><td>May</td><td></td><td>115K</td><td>130K</td><td>125K</td><td></td></tr>
        </table>
        """
        after = before.replace("<td></td><td>115K</td>", "<td>140K</td><td>115K</td>")
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "monthly_backfill" / "trading_economics_calendar_web"
            task_key = {
                "task_id": "te_calendar_recent_bucket_changed_test",
                "feed": "07_feed_trading_economics_calendar_web",
                "params": {
                    "html": before,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-30",
                    "importance": "3",
                    "date_range_mode": "recent",
                    "monthly_backfill_bucketed_output": True,
                },
                "output_root": str(output_root),
            }

            self.assertEqual(run(task_key, run_id="run1").status, "succeeded")
            task_key["params"]["html"] = after
            self.assertEqual(run(task_key, run_id="run2").status, "succeeded")
            self.assertTrue((output_root / "2026-06" / "runs" / "run2" / "saved" / "trading_economics_calendar_event.csv").exists())

    def test_future_preview_returns_release_fetch_candidate(self):
        html = """
        <table>
          <tr><th>Date</th><th>Country</th><th>Event</th><th>Category</th><th>Reference</th><th>Actual</th><th>Previous</th><th>Consensus</th><th>Forecast</th><th>Revised</th></tr>
          <tr><td>2099-01-04 08:30</td><td>United States</td><td>Non Farm Payrolls</td><td>Labour</td><td>Dec</td><td></td><td>115K</td><td>130K</td><td>125K</td><td></td></tr>
        </table>
        """
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "monthly_backfill" / "trading_economics_calendar_web"
            task_key = {
                "task_id": "te_calendar_future_preview_candidate_test",
                "feed": "07_feed_trading_economics_calendar_web",
                "params": {
                    "html": html,
                    "start_date": "2099-01-01",
                    "end_date": "2099-01-31",
                    "importance": "3",
                    "date_range_mode": "recent",
                    "monthly_backfill_bucketed_output": True,
                },
                "output_root": str(output_root),
            }

            result = run(task_key, run_id="run1")
            candidate = result.details["release_fetch_candidates"][0]

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(candidate["fetch_after_utc"], "2099-01-04T13:30:00Z")
            self.assertEqual(candidate["start_date"], "2099-01-04")
            self.assertEqual(candidate["end_date"], "2099-01-05")

    def test_custom_mode_uses_range_cookie(self):
        params = {"date_range_mode": "custom", "use_authenticated_cookies": False, "start_date": "2018-10-01", "end_date": "2018-11-01", "importance": "3"}
        self.assertIn("cal-custom-range=2018-10-01 00:00|2018-11-01 00:00", te_pipeline._cookie_header(params, cookie_jar=Path("/tmp/no-such-te-cookie-file")))

    def test_custom_mode_defaults_to_no_authenticated_cookies(self):
        params = {"date_range_mode": "custom", "start_date": "2018-10-01", "end_date": "2018-11-01", "importance": "3"}
        self.assertFalse(te_pipeline._use_authenticated_cookies(params))
        cookie_header = te_pipeline._cookie_header(params, cookie_jar=Path("/tmp/no-such-te-cookie-file"))
        self.assertIn("cal-custom-range=2018-10-01 00:00|2018-11-01 00:00", cookie_header)

    def test_requires_explicit_html_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "te_calendar_task_no_fetch",
                "feed": "07_feed_trading_economics_calendar_web",
                "params": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.details["error"]["type"], "TradingEconomicsCalendarError")

    def test_failure_diagnostics_capture_structure_without_raw_request_state(self):
        html = """
        <html><body>
          <table id="calendar">
            <thead><tr><th colspan='3'>Friday January 08 2016</th><th>Actual</th><th>Previous</th><th>Consensus</th><th>Forecast</th></tr></thead>
            <tr data-url="/united-states/non-farm-payrolls" data-country="united states" data-category="non farm payrolls" data-event="non farm payrolls">
              <td class=' 2016-01-08'><span class="event-38 calendar-date-3">08:30 AM</span></td>
              <td><a class='calendar-event'>Non Farm Payrolls</a></td>
              <td><span id='actual'>292K</span></td><td><span id='previous'>252K</span></td><td><span id='consensus'>200K</span></td><td><span id='forecast'>205K</span></td>
            </tr>
          </table>
        </body></html>
        """
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "te_calendar_failure_diagnostic_test",
                "feed": "07_feed_trading_economics_calendar_web",
                "params": {
                    "html": html,
                    "start_date": "2016-02-01",
                    "end_date": "2016-03-01",
                    "importance": "3",
                    "persist_failure_diagnostics": True,
                },
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "failed")
            diagnostic_path = Path(task_key["output_root"]) / "runs" / "run" / "diagnostics" / "te_calendar_failure_diagnostic.json"
            diagnostic = json.loads(diagnostic_path.read_text())
            self.assertEqual(diagnostic["contract_type"], "trading_economics_calendar_web_failure_diagnostic")
            self.assertEqual(diagnostic["parsed_rows_count"], 1)
            self.assertEqual(diagnostic["in_window_rows_count"], 0)
            self.assertEqual(diagnostic["structural_counts"]["data_url_rows"], 1)
            self.assertNotIn("Cookie", json.dumps(diagnostic))


if __name__ == "__main__":
    unittest.main()
