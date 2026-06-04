from __future__ import annotations

import json
import subprocess
import sys
import unittest

from scripts.data.run_calendar_maintenance_refresh import (
    build_nasdaq_earnings_task_key,
    run_calendar_maintenance,
)


class CalendarMaintenanceRefreshTests(unittest.TestCase):
    def test_nasdaq_earnings_task_key_defaults_to_closed_provider_gate(self) -> None:
        task_key = build_nasdaq_earnings_task_key(calendar_date="2026-06-05", symbols=["AAPL"])

        self.assertEqual(task_key["feed"], "12_feed_official_calendar_discovery")
        self.assertEqual(task_key["params"]["data_kind"], "nasdaq_earnings_calendar")
        self.assertEqual(task_key["params"]["symbols"], ["AAPL"])
        self.assertFalse(task_key["manager_controls"]["allow_live_provider_calls"])
        self.assertEqual(task_key["manager_controls"]["allowed_providers"], ["nasdaq"])
        self.assertEqual(task_key["manager_controls"]["allowed_endpoint_families"], ["calendar_discovery"])

    def test_execute_nasdaq_task_key_opens_provider_gate(self) -> None:
        task_key = build_nasdaq_earnings_task_key(calendar_date="2026-06-05", allow_live_fetch=True)

        self.assertTrue(task_key["manager_controls"]["allow_live_provider_calls"])
        self.assertTrue(task_key["manager_controls"]["realtime_provider_maintenance"])

    def test_calendar_maintenance_plan_runs_no_provider_calls(self) -> None:
        receipt = run_calendar_maintenance(
            run_id="plan",
            execute_live_fetch=False,
            te_start_date="2026-06-01",
            te_end_date="2026-06-05",
            te_trailing_days=0,
            te_forward_days=1,
            te_output_root="/tmp/te",
            nasdaq_earnings_start_date="2026-06-01",
            nasdaq_earnings_forward_days=1,
            official_output_root="/tmp/official",
            symbols=["AAPL"],
        )

        self.assertEqual(receipt["refresh_status"], "planned_requires_execute_live_fetch")
        self.assertEqual(receipt["provider_calls_performed"], 0)
        self.assertFalse(receipt["storage_mutation_performed"])
        official = receipt["components"]["official_calendar_discovery"]
        self.assertEqual(len(official["task_keys"]), 2)

    def test_cli_plan_is_side_effect_safe(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/data/run_calendar_maintenance_refresh.py",
                "--te-start-date",
                "2026-06-01",
                "--te-end-date",
                "2026-06-05",
                "--nasdaq-earnings-start-date",
                "2026-06-01",
                "--nasdaq-earnings-forward-days",
                "0",
                "--symbol",
                "AAPL",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["refresh_status"], "planned_requires_execute_live_fetch")
        self.assertEqual(payload["provider_calls_performed"], 0)
        self.assertFalse(payload["storage_mutation_performed"])


if __name__ == "__main__":
    unittest.main()

