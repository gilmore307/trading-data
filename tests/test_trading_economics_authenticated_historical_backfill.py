import tempfile
import unittest
from pathlib import Path

from scripts.data.run_trading_economics_authenticated_historical_backfill import (
    MonthBackfillResult,
    _summary_payload,
    _task_key,
)


class TradingEconomicsAuthenticatedHistoricalBackfillTests(unittest.TestCase):
    def test_task_key_authorizes_authenticated_monthly_historical_fetch(self) -> None:
        task_key = _task_key(month="2016-01", output_root="/tmp/te", write_only_changed=False)

        self.assertEqual(task_key["feed"], "07_feed_trading_economics_calendar_web")
        self.assertEqual(task_key["params"]["start_date"], "2016-01-01")
        self.assertEqual(task_key["params"]["end_date"], "2016-02-01")
        self.assertEqual(task_key["params"]["date_range_mode"], "custom")
        self.assertTrue(task_key["params"]["use_authenticated_cookies"])
        self.assertFalse(task_key["params"]["write_only_changed_monthly_buckets"])
        self.assertTrue(task_key["manager_controls"]["allow_live_provider_calls"])
        self.assertTrue(task_key["manager_controls"]["autonomous_historical_provider_acquisition"])
        self.assertEqual(task_key["manager_controls"]["allowed_endpoint_families"], ["calendar_web"])
        self.assertIn("no_api_download_or_export_endpoint", task_key["policy_refs"])

    def test_summary_counts_actual_previous_consensus_forecast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = MonthBackfillResult(
                month="2016-01",
                status="succeeded",
                run_id="run",
                row_count=2,
                actual_count=2,
                previous_count=2,
                consensus_count=1,
                forecast_count=1,
                saved_paths=(str(Path(tmp) / "rows.csv"),),
            )
            summary = _summary_payload(
                run_group_id="group",
                months=["2016-01"],
                results=[result],
                output_root=tmp,
            )

        self.assertEqual(summary["completed_month_count"], 1)
        self.assertEqual(summary["failed_month_count"], 0)
        self.assertEqual(summary["field_totals"]["rows"], 2)
        self.assertEqual(summary["field_totals"]["actual"], 2)
        self.assertEqual(summary["field_totals"]["previous"], 2)
        self.assertEqual(summary["field_totals"]["consensus"], 1)
        self.assertEqual(summary["field_totals"]["forecast"], 1)
        self.assertFalse(summary["database_writes_performed"])
        self.assertFalse(summary["model_training_performed"])


if __name__ == "__main__":
    unittest.main()
