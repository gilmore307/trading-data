from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from data_sources.sec_company_financials.pipeline import run
from source_availability.http import HttpResult


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
                "task_id": "sec_company_financials_task_test",
                "bundle": "sec_company_financials",
                "params": {"data_kind": "sec_company_concept", "cik": "320193", "taxonomy": "us-gaap", "tag": "Assets"},
                "output_root": str(Path(tmp) / "sec_company_financials_task_test"),
            }
            client = FakeSecClient(payload)
            result = run(task_key, run_id="sec_company_financials_run_test", client=client, sec_user_agent="test@example.com")
            self.assertEqual(result.status, "succeeded")
            self.assertIn("CIK0000320193/us-gaap/Assets.json", client.requests[0][0])
            self.assertEqual(client.requests[0][2]["User-Agent"], "test@example.com")
            saved = Path(task_key["output_root"]) / "runs" / "sec_company_financials_run_test" / "saved" / "sec_company_concept.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["cik"], "320193")
            self.assertEqual(row["tag"], "Assets")
            self.assertEqual(row["value"], "352583000000")
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
            task_key = {"task_id": "sec_company_financials_task_fact", "bundle": "sec_company_financials", "params": {"data_kind": "sec_company_fact", "cik": "0000320193", "taxonomy": "us-gaap", "tag": "Assets", "unit": "USD"}, "output_root": str(Path(tmp) / "task")}
            result = run(task_key, run_id="run", client=FakeSecClient(payload), sec_user_agent="test")
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["sec_company_fact"], 1)

    def test_submission_rows_flatten_recent_filings(self):
        payload = {
            "name": "Apple Inc.",
            "filings": {"recent": {"accessionNumber": ["a1"], "filingDate": ["2024-01-01"], "reportDate": ["2023-12-31"], "form": ["10-K"], "primaryDocument": ["a.htm"], "primaryDocDescription": ["10-K"]}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "sec_company_financials_task_sub", "bundle": "sec_company_financials", "params": {"data_kind": "sec_submission", "cik": "320193"}, "output_root": str(Path(tmp) / "task")}
            result = run(task_key, run_id="run", client=FakeSecClient(payload), sec_user_agent="test")
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["sec_submission"], 1)

    def test_bad_kind_writes_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "sec_company_financials_task_bad", "bundle": "sec_company_financials", "params": {"data_kind": "bad", "cik": "320193"}, "output_root": str(Path(tmp) / "task")}
            result = run(task_key, run_id="run", client=FakeSecClient({}), sec_user_agent="test")
            self.assertEqual(result.status, "failed")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["error"]["type"], "SecCompanyFinancialsError")


if __name__ == "__main__":
    unittest.main()
