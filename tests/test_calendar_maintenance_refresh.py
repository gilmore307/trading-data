from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.data.run_calendar_maintenance_refresh import (
    build_nasdaq_earnings_task_key,
    build_official_exchange_calendar_task_key,
    queue_te_release_fetches,
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

    def test_official_exchange_calendar_task_key_uses_nyse_source(self) -> None:
        task_key = build_official_exchange_calendar_task_key(allow_live_fetch=True)

        self.assertEqual(task_key["params"]["data_kind"], "official_exchange_calendar")
        self.assertEqual(task_key["params"]["source_url"], "https://www.nyse.com/trade/hours-calendars")
        self.assertEqual(task_key["manager_controls"]["allowed_providers"], ["official_exchange"])
        self.assertTrue(task_key["manager_controls"]["allow_live_provider_calls"])

    def test_calendar_maintenance_plan_runs_no_provider_calls(self) -> None:
        receipt = run_calendar_maintenance(
            run_id="plan",
            execute_live_fetch=False,
            skip_trading_economics=False,
            te_start_date="2026-06-01",
            te_end_date="2026-06-05",
            te_trailing_days=0,
            te_forward_days=1,
            te_output_root="/tmp/te",
            nasdaq_earnings_start_date="2026-06-01",
            nasdaq_earnings_forward_days=1,
            official_output_root="/tmp/official",
            symbols=["AAPL"],
            queue_te_release_fetches_enabled=False,
            te_release_fetch_delay_seconds=0,
            te_release_fetch_max_count=48,
            te_release_poll_interval_seconds=5,
            te_release_poll_timeout_seconds=60,
        )

        self.assertEqual(receipt["refresh_status"], "planned_requires_execute_live_fetch")
        self.assertEqual(receipt["provider_calls_performed"], 0)
        self.assertFalse(receipt["storage_mutation_performed"])
        official = receipt["components"]["official_calendar_discovery"]
        self.assertEqual(len(official["task_keys"]), 2)
        exchange = receipt["components"]["official_exchange_calendar"]
        self.assertEqual(exchange["task_key"]["params"]["data_kind"], "official_exchange_calendar")
        self.assertIsNone(receipt["components"]["temporal_explorer_session_overlay"])
        te = receipt["components"]["trading_economics_recent_calendar"]
        self.assertTrue(te["task_key"]["params"]["use_authenticated_cookies"])
        self.assertTrue(te["task_key"]["manager_controls"]["authenticated_provider_session_required"])

    def test_calendar_maintenance_can_skip_trading_economics(self) -> None:
        receipt = run_calendar_maintenance(
            run_id="plan",
            execute_live_fetch=False,
            skip_trading_economics=True,
            te_start_date=None,
            te_end_date=None,
            te_trailing_days=7,
            te_forward_days=35,
            te_output_root="/tmp/te",
            nasdaq_earnings_start_date="2026-06-01",
            nasdaq_earnings_forward_days=0,
            official_output_root="/tmp/official",
            symbols=["AAPL"],
            queue_te_release_fetches_enabled=False,
            te_release_fetch_delay_seconds=0,
            te_release_fetch_max_count=48,
            te_release_poll_interval_seconds=5,
            te_release_poll_timeout_seconds=60,
        )

        te = receipt["components"]["trading_economics_recent_calendar"]
        self.assertEqual(te["refresh_status"], "skipped")
        self.assertEqual(te["provider_calls_performed"], 0)
        self.assertFalse(te["storage_mutation_performed"])
        self.assertEqual(receipt["refresh_status"], "planned_requires_execute_live_fetch")

    def test_te_release_fetch_queue_plans_fetch(self) -> None:
        receipt = {
            "task_key": {"output_root": "/tmp/te-calendar"},
            "result": {
                "details": {
                    "release_fetch_candidates": [
                        {
                            "fetch_after_utc": "2099-01-04T13:30:00Z",
                            "start_date": "2099-01-04",
                            "end_date": "2099-01-05",
                            "event_count": 3,
                            "events": [
                                {
                                    "country": "United States",
                                    "event": "Non Farm Payrolls",
                                    "reference": "Dec",
                                    "source_event_type": "non farm payrolls",
                                }
                            ],
                        }
                    ]
                }
            },
        }

        update = queue_te_release_fetches(te_receipt=receipt, delay_seconds=0, max_count=48, poll_interval_seconds=5, poll_timeout_seconds=60, execute=False)
        planned = update["queued"][0]

        self.assertEqual(update["queue_status"], "planned")
        self.assertEqual(update["delay_seconds"], 0)
        self.assertEqual(update["poll_interval_seconds"], 5)
        self.assertEqual(update["poll_timeout_seconds"], 60)
        self.assertEqual(update["candidate_count"], 1)
        self.assertEqual(planned["status"], "planned")
        self.assertNotIn("command", planned)
        self.assertEqual(planned["start_date"], "2099-01-04")
        self.assertEqual(planned["end_date"], "2099-01-05")
        self.assertIn("United States Non Farm Payrolls Dec actual released", planned["fallback_queries"])

    def test_te_release_fetch_queue_writes_pending_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt = {
                "task_key": {"output_root": str(Path(tmp) / "te-calendar")},
                "result": {
                    "details": {
                        "release_fetch_candidates": [
                            {
                                "fetch_after_utc": "2099-01-04T13:30:00Z",
                                "start_date": "2099-01-04",
                                "end_date": "2099-01-05",
                                "event_count": 1,
                                "events": [{"country": "United States", "event": "CPI", "reference": "Dec"}],
                            }
                        ]
                    }
                },
            }

            update = queue_te_release_fetches(te_receipt=receipt, delay_seconds=0, max_count=48, poll_interval_seconds=5, poll_timeout_seconds=60, execute=True)
            queue_path = Path(update["queue_path"])
            payload = json.loads(queue_path.read_text(encoding="utf-8"))

        self.assertEqual(update["queue_status"], "queued")
        self.assertEqual(update["written_count"], 1)
        self.assertEqual(payload["contract_type"], "trading_economics_release_fetch_queue")
        self.assertEqual(payload["items"][0]["status"], "pending")
        self.assertEqual(payload["items"][0]["fallback_queries"], ["United States CPI Dec actual released"])

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

    def test_cli_reads_symbols_file_from_environment(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            handle.write("aapl,nvda\n")
            handle.flush()
            env = dict(os.environ)
            env["TRADING_DATA_CALENDAR_SYMBOLS_FILE"] = handle.name
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
                ],
                check=True,
                capture_output=True,
                env=env,
                text=True,
            )
        payload = json.loads(completed.stdout)
        task_key = payload["components"]["official_calendar_discovery"]["task_keys"][0]

        self.assertEqual(task_key["params"]["symbols"], ["AAPL", "NVDA"])
        self.assertEqual(payload["provider_calls_performed"], 0)

    def test_cli_configured_missing_symbols_file_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["TRADING_DATA_CALENDAR_SYMBOLS_FILE"] = str(Path(tmp) / "missing.symbols.txt")
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
                ],
                check=True,
                capture_output=True,
                env=env,
                text=True,
            )
        payload = json.loads(completed.stdout)
        task_key = payload["components"]["official_calendar_discovery"]["task_keys"][0]

        self.assertEqual(task_key["params"]["symbols"], [])
        self.assertEqual(payload["provider_calls_performed"], 0)


if __name__ == "__main__":
    unittest.main()
