import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scripts.data.run_calendar_maintenance_refresh import release_fetch_queue_path
from scripts.data.run_trading_economics_release_fetcher import run_release_fetch_queue


class TradingEconomicsReleaseFetcherTests(unittest.TestCase):
    def test_fetcher_processes_due_pending_job(self) -> None:
        now = datetime(2099, 1, 4, 13, 31, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "te"
            queue_path = release_fetch_queue_path(output_root)
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text(
                json.dumps(
                    {
                        "contract_type": "trading_economics_release_fetch_queue",
                        "schema_version": 1,
                        "items": [
                            {
                                "job_id": "te_release_fetch_2099-01-04-2099-01-04t13-30-00z",
                                "run_id": "te_release_fetch_2099010420990104t133000z",
                                "fetch_after_utc": "2099-01-04T13:30:00Z",
                                "start_date": "2099-01-04",
                                "end_date": "2099-01-05",
                                "fallback_queries": ["United States CPI Dec actual released"],
                                "poll_interval_seconds": 5,
                                "poll_timeout_seconds": 60,
                                "status": "pending",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("scripts.data.run_trading_economics_release_fetcher.run_release_poll") as poll:
                poll.return_value = {
                    "refresh_status": "succeeded",
                    "provider_calls_performed": 1,
                    "storage_mutation_performed": True,
                    "release_poll": {"poll_status": "te_released_value_available"},
                }
                receipt = run_release_fetch_queue(output_root=str(output_root), execute_live_fetch=True, max_due_jobs=8, now=now)
            payload = json.loads(queue_path.read_text(encoding="utf-8"))

        self.assertEqual(receipt["run_status"], "processed_due_jobs")
        self.assertEqual(receipt["processed_count"], 1)
        self.assertEqual(payload["items"][0]["status"], "completed")
        self.assertEqual(payload["items"][0]["last_result"]["refresh_status"], "succeeded")

    def test_fetcher_ignores_future_pending_job(self) -> None:
        now = datetime(2099, 1, 4, 13, 29, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "te"
            queue_path = release_fetch_queue_path(output_root)
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text(
                json.dumps(
                    {
                        "contract_type": "trading_economics_release_fetch_queue",
                        "schema_version": 1,
                        "items": [
                            {
                                "job_id": "te_release_fetch_future",
                                "run_id": "te_release_fetch_future",
                                "fetch_after_utc": "2099-01-04T13:30:00Z",
                                "start_date": "2099-01-04",
                                "end_date": "2099-01-05",
                                "status": "pending",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            receipt = run_release_fetch_queue(output_root=str(output_root), execute_live_fetch=True, max_due_jobs=8, now=now)
            payload = json.loads(queue_path.read_text(encoding="utf-8"))

        self.assertEqual(receipt["run_status"], "idle_no_due_jobs")
        self.assertEqual(receipt["processed_count"], 0)
        self.assertEqual(payload["items"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
