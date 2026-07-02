import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.data.run_trading_economics_recent_calendar_refresh import build_recent_calendar_task_key, run_release_poll, run_web_search_fallback


class TradingEconomicsRecentCalendarRefreshTests(unittest.TestCase):
    def test_plan_builds_recent_mode_task_key_with_closed_provider_gate(self) -> None:
        task_key = build_recent_calendar_task_key(start_date="2026-05-18", end_date="2026-06-12")

        self.assertEqual(task_key["feed"], "07_feed_trading_economics_calendar_web")
        self.assertEqual(task_key["output_root"], "/root/projects/trading-storage/storage/01_source_data/monthly_backfill/trading_economics_calendar_web")
        self.assertEqual(task_key["params"]["date_range_mode"], "recent")
        self.assertTrue(task_key["params"]["monthly_backfill_bucketed_output"])
        self.assertFalse(task_key["params"]["use_authenticated_cookies"])
        self.assertFalse(task_key["manager_controls"]["allow_live_provider_calls"])
        self.assertFalse(task_key["params"]["allow_live_fetch"])
        self.assertNotIn("authenticated_provider_session_required", task_key["manager_controls"])
        self.assertEqual(task_key["manager_controls"]["allowed_providers"], ["trading_economics"])
        self.assertEqual(task_key["manager_controls"]["max_requests"], 1)

    def test_cli_plan_requires_explicit_execute_live_fetch(self) -> None:
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

        self.assertEqual(payload["refresh_status"], "planned_requires_execute_live_fetch")
        self.assertEqual(payload["provider_calls_performed"], 0)
        self.assertFalse(payload["storage_mutation_performed"])

    def test_execute_task_key_opens_bounded_provider_gate(self) -> None:
        task_key = build_recent_calendar_task_key(
            start_date="2026-05-18",
            end_date="2026-06-12",
            allow_live_fetch=True,
        )

        self.assertTrue(task_key["params"]["allow_live_fetch"])
        self.assertFalse(task_key["params"]["use_authenticated_cookies"])
        self.assertTrue(task_key["manager_controls"]["allow_live_provider_calls"])
        self.assertNotIn("authenticated_provider_session_required", task_key["manager_controls"])
        self.assertEqual(task_key["manager_controls"]["allowed_endpoint_families"], ["calendar_web"])
        self.assertNotIn("source" + "_url", json.dumps(task_key))

    def test_task_key_can_explicitly_enable_authenticated_cookies(self) -> None:
        task_key = build_recent_calendar_task_key(
            start_date="2026-05-18",
            end_date="2026-06-12",
            use_authenticated_cookies=True,
        )

        self.assertTrue(task_key["params"]["use_authenticated_cookies"])
        self.assertNotIn("authenticated_provider_session_required", task_key["manager_controls"])

    def test_release_poll_falls_back_to_web_search_after_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_key = build_recent_calendar_task_key(
                start_date="2099-01-04",
                end_date="2099-01-05",
                output_root=str(Path(tmp) / "te"),
                allow_live_fetch=True,
            )

            def fake_refresh(*, task_key, run_id, execute_live_fetch):
                return {
                    "contract_type": "trading_economics_recent_calendar_refresh_receipt",
                    "refresh_status": "skipped_no_new_or_changed_rows",
                    "run_id": run_id,
                    "task_key": task_key,
                    "result": {"references": []},
                    "provider_calls_performed": 1,
                    "storage_mutation_performed": False,
                }

            def fake_search(query, **kwargs):
                return [{"title": "NFP actual 150K", "url": "https://example.test/release", "description": query}]

            with patch("scripts.data.run_trading_economics_recent_calendar_refresh.run_refresh", fake_refresh):
                with patch("scripts.data.run_trading_economics_recent_calendar_refresh.run_web_search_fallback") as fallback:
                    fallback.side_effect = lambda **kwargs: {
                        "contract_type": "provisional_macro_release_web_search_receipt",
                        "fallback_status": "succeeded",
                        "reference": str(Path(tmp) / "te" / "_manifests" / "release_fetch_fallbacks" / "poll" / "provisional_macro_release_web_search.json"),
                        "query_count": 1,
                        "result_count": len(fake_search("query")),
                        "error": None,
                    }
                    receipt = run_release_poll(
                        task_key=task_key,
                        run_id="poll",
                        execute_live_fetch=True,
                        poll_interval_seconds=5,
                        poll_timeout_seconds=0,
                        fallback_web_search_after_timeout=True,
                        fallback_queries=["United States Non Farm Payrolls actual released"],
                    )

        self.assertEqual(receipt["release_poll"]["poll_status"], "fallback_requested")
        self.assertEqual(receipt["release_poll"]["attempts"][0]["released_value_available"], False)
        self.assertEqual(receipt["release_poll"]["fallback_web_search"]["fallback_status"], "succeeded")

    def test_web_search_fallback_writes_provisional_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_key = build_recent_calendar_task_key(
                start_date="2099-01-04",
                end_date="2099-01-05",
                output_root=str(Path(tmp) / "te"),
                allow_live_fetch=True,
            )

            receipt = run_web_search_fallback(
                task_key=task_key,
                run_id="fallback",
                fallback_queries=["United States Non Farm Payrolls actual released"],
                search_fn=lambda query, **kwargs: [{"title": "NFP actual 150K", "url": "https://example.test/release", "description": query}],
            )
            payload = json.loads(Path(receipt["reference"]).read_text(encoding="utf-8"))

        self.assertEqual(receipt["fallback_status"], "succeeded")
        self.assertEqual(payload["contract_type"], "provisional_macro_release_web_search")
        self.assertEqual(payload["source_role"], "provisional_realtime_decision_fallback")
        self.assertEqual(payload["query_results"][0]["results"][0]["title"], "NFP actual 150K")
        self.assertIn("formal Trading Economics", payload["replacement_policy"])


if __name__ == "__main__":
    unittest.main()
