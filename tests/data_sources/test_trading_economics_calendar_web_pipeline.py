import csv
import json
import tempfile
import unittest
from pathlib import Path

from trading_data.data_sources.trading_economics_calendar_web.pipeline import run


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
                "bundle": "trading_economics_calendar_web",
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

    def test_requires_explicit_html_or_live_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "te_calendar_task_no_fetch",
                "bundle": "trading_economics_calendar_web",
                "params": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.details["error"]["type"], "TradingEconomicsCalendarError")


if __name__ == "__main__":
    unittest.main()
