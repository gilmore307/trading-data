import json
import subprocess
import sys
import unittest

from scripts.data.run_trading_economics_recent_calendar_refresh import build_recent_calendar_task_key


class TradingEconomicsRecentCalendarRefreshTests(unittest.TestCase):
    def test_plan_builds_recent_mode_task_key_with_closed_provider_gate(self) -> None:
        task_key = build_recent_calendar_task_key(start_date="2026-05-18", end_date="2026-06-12")

        self.assertEqual(task_key["feed"], "07_feed_trading_economics_calendar_web")
        self.assertEqual(task_key["output_root"], "storage/monthly_backfill/trading_economics_calendar_web")
        self.assertEqual(task_key["params"]["date_range_mode"], "recent")
        self.assertTrue(task_key["params"]["monthly_backfill_bucketed_output"])
        self.assertFalse(task_key["params"]["use_authenticated_cookies"])
        self.assertFalse(task_key["manager_controls"]["allow_live_provider_calls"])
        self.assertEqual(task_key["manager_controls"]["allowed_providers"], [])
        self.assertEqual(task_key["manager_controls"]["max_requests"], 0)

    def test_cli_plan_is_retired_storage_source_only(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/data/run_trading_economics_recent_calendar_refresh.py",
                "--start-date",
                "2026-05-18",
                "--end-date",
                "2026-06-12",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["refresh_status"], "retired_storage_source_only")
        self.assertEqual(payload["provider_calls_performed"], 0)
        self.assertFalse(payload["storage_mutation_performed"])

    def test_execute_live_fetch_is_rejected(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/data/run_trading_economics_recent_calendar_refresh.py",
                "--start-date",
                "2026-05-18",
                "--end-date",
                "2026-06-12",
                "--execute-live-fetch",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(payload["refresh_status"], "rejected_retired_storage_source_only")
        self.assertEqual(payload["provider_calls_performed"], 0)
        self.assertFalse(payload["storage_mutation_performed"])


if __name__ == "__main__":
    unittest.main()
