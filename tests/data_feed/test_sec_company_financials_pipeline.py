from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from importlib import import_module
from tests.data_feed.fake_sql import FakeSqlWriter

run = import_module("data_feed.08_feed_sec_company_financials.pipeline").run
from feed_availability.http import HttpResult


class FakeSecClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def get(self, url, *, params=None, headers=None):
        self.requests.append((url, params, headers))
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(self.payload).encode())


class SecCompanyFinancialsPipelineTests(unittest.TestCase):
    def test_company_concept_fetch_clean_save_receipt(self):
        payload = {
            "cik": 320193,
            "entityName": "Apple Inc.",
            "label": "Assets",
            "description": "Assets description",
            "units": {
                "USD": [
                    {"fy": 2023, "fp": "FY", "form": "10-K", "filed": "2023-11-03", "frame": "CY2023Q3I", "end": "2023-09-30", "val": 352583000000, "accn": "0000320193-23-000106"}
                ]
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "08_feed_sec_company_financials_task_test",
                "feed": "08_feed_sec_company_financials",
                "params": {"data_kind": "sec_company_concept", "cik": "320193", "taxonomy": "us-gaap", "tag": "Assets"},
                "output_root": str(Path(tmp) / "08_feed_sec_company_financials_task_test"),
            }
            client = FakeSecClient(payload)
            writer = FakeSqlWriter()
            result = run(task_key, run_id="08_feed_sec_company_financials_run_test", client=client, client_is_fixture=True, sec_user_agent="test@example.com", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertIn("CIK0000320193/us-gaap/Assets.json", client.requests[0][0])
            self.assertEqual(client.requests[0][2]["User-Agent"], "test@example.com")
            row = writer.rows_for("feed_08_sec_company_concept")[0]
            self.assertEqual(row["cik"], "320193")
            self.assertEqual(row["tag"], "Assets")
            self.assertEqual(row["value"], 352583000000)
            run_dir = Path(task_key["output_root"]) / "runs" / "08_feed_sec_company_financials_run_test"
            self.assertFalse((run_dir / "saved/sec_company_concept.csv").exists())
            self.assertFalse((run_dir / "cleaned/sec_company_concept.jsonl").exists())
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["row_counts"]["sec_company_concept"], 1)

    def test_companyfacts_filter_by_tag_and_unit(self):
        payload = {
            "cik": 320193,
            "entityName": "Apple Inc.",
            "facts": {
                "us-gaap": {
                    "Assets": {"label": "Assets", "units": {"USD": [{"val": 1, "fy": 2024, "fp": "Q1", "form": "10-Q", "filed": "2024-01-01", "end": "2023-12-31", "accn": "a"}], "shares": [{"val": 2}]}},
                    "Liabilities": {"label": "Liabilities", "units": {"USD": [{"val": 3}]}}
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "08_feed_sec_company_financials_task_fact", "feed": "08_feed_sec_company_financials", "params": {"data_kind": "sec_company_fact", "cik": "0000320193", "taxonomy": "us-gaap", "tag": "Assets", "unit": "USD"}, "output_root": str(Path(tmp) / "task")}
            result = run(task_key, run_id="run", client=FakeSecClient(payload), client_is_fixture=True, sec_user_agent="test", sql_writer=FakeSqlWriter())
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["sec_company_fact"], 1)

    def test_submission_rows_flatten_recent_filings(self):
        payload = {
            "name": "Apple Inc.",
            "filings": {"recent": {"accessionNumber": ["a1"], "filingDate": ["2024-01-01"], "reportDate": ["2023-12-31"], "acceptanceDateTime": ["2024-01-01T16:02:03.000Z"], "form": ["10-K"], "primaryDocument": ["a.htm"], "primaryDocDescription": ["10-K"]}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "08_feed_sec_company_financials_task_sub", "feed": "08_feed_sec_company_financials", "params": {"data_kind": "sec_submission", "cik": "320193"}, "output_root": str(Path(tmp) / "task")}
            writer = FakeSqlWriter()
            result = run(task_key, run_id="run", client=FakeSecClient(payload), client_is_fixture=True, sec_user_agent="test", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["sec_submission"], 1)
            row = writer.rows_for("feed_08_sec_submission")[0]
            self.assertEqual(row["acceptance_datetime"], "2024-01-01T16:02:03.000Z")

    def test_filing_document_fetch_saves_metadata_and_text_artifact(self):
        payload = "<html><body>Company reports earnings and updates outlook.</body></html>"
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "08_feed_sec_company_financials_task_doc",
                "feed": "08_feed_sec_company_financials",
                "params": {
                    "data_kind": "sec_filing_document",
                    "cik": "320193",
                    "accession_number": "0000320193-24-000001",
                    "document_name": "aapl-20240101.htm",
                },
                "output_root": str(Path(tmp) / "task"),
            }
            client = FakeSecClient(payload)
            writer = FakeSqlWriter()
            result = run(task_key, run_id="run", client=client, client_is_fixture=True, sec_user_agent="test", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["sec_filing_document"], 1)
            self.assertIn("/Archives/edgar/data/320193/000032019324000001/aapl-20240101.htm", client.requests[0][0])
            run_dir = Path(task_key["output_root"]) / "runs" / "run"
            row = writer.rows_for("feed_08_sec_filing_document")[0]
            self.assertEqual(row["accession_number"], "0000320193-24-000001")
            self.assertEqual(row["document_name"], "aapl-20240101.htm")
            self.assertTrue(row["text_sha256"])
            text_path = Path(row["document_text_path"])
            self.assertTrue(text_path.exists())
            self.assertIn("updates outlook", text_path.read_text(encoding="utf-8"))
            self.assertFalse((run_dir / "saved/sec_filing_document.csv").exists())

    def test_bad_kind_writes_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "08_feed_sec_company_financials_task_bad", "feed": "08_feed_sec_company_financials", "params": {"data_kind": "bad", "cik": "320193"}, "output_root": str(Path(tmp) / "task")}
            result = run(task_key, run_id="run", client=FakeSecClient({}), client_is_fixture=True, sec_user_agent="test")
            self.assertEqual(result.status, "failed")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["error"]["type"], "SecCompanyFinancialsError")


if __name__ == "__main__":
    unittest.main()
