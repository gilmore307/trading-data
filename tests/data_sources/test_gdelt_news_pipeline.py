from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from trading_data.data_sources.gdelt_news.pipeline import run


class FakeBigQueryResult:
    def __init__(self, rows):
        self.rows = rows


class FakeBigQueryClient:
    def __init__(self, rows):
        self.rows = rows
        self.requests = []

    def query(self, sql, *, max_results=None, maximum_bytes_billed=None, dry_run=False):
        self.requests.append((sql, max_results, maximum_bytes_billed, dry_run))
        return FakeBigQueryResult(self.rows)


class GdeltNewsPipelineTests(unittest.TestCase):
    def test_gdelt_news_fetch_clean_save_receipt(self):
        rows = [
            {
                "article_id": "20260427123000-1",
                "gdelt_date": "20260427123000",
                "source_domain": "example.com",
                "url": "https://example.com/politics-economy-tech",
                "source_theme_tags": "ECON_STOCKMARKET;TAX_FNCACT",
                "persons": "",
                "organizations": "Federal Reserve",
                "locations": "US#United States#US",
                "tone": "-1.2,2.0,3.2",
                "sharing_image": "https://example.com/image.jpg",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "gdelt_news_task_test",
                "bundle": "gdelt_news",
                "params": {"query_terms": ["inflation", "semiconductor"], "start_date": "2026-04-27", "end_date": "2026-04-27", "max_rows": 10},
                "output_root": str(Path(tmp) / "gdelt_news_task_test"),
            }
            client = FakeBigQueryClient(rows)
            result = run(task_key, run_id="gdelt_news_run_test", client=client)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["gdelt_article"], 1)
            sql, max_results, maximum_bytes_billed, dry_run = client.requests[0]
            self.assertIn("gdelt-bq.gdeltv2.gkg_partitioned", sql)
            self.assertIn("united states", sql.lower())
            self.assertIn("reuters.com", sql.lower())
            self.assertEqual(max_results, 10)
            self.assertIsNone(maximum_bytes_billed)
            self.assertFalse(dry_run)
            saved = Path(task_key["output_root"]) / "runs" / "gdelt_news_run_test" / "saved" / "gdelt_article.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["article_id"], "20260427123000-1")
            self.assertEqual(row["seen_at_utc"], "2026-04-27T12:30:00Z")
            self.assertEqual(row["tone"], "-1.2")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["row_counts"]["gdelt_article"], 1)

    def test_default_topics_allow_omitting_query_terms(self):
        rows = [{"article_id": "a", "gdelt_date": "20260427123000", "source_domain": "reuters.com", "url": "https://reuters.com/a"}]
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "gdelt_news_task_default", "bundle": "gdelt_news", "params": {"max_rows": 1}, "output_root": str(Path(tmp) / "task")}
            client = FakeBigQueryClient(rows)
            result = run(task_key, run_id="run", client=client)
            self.assertEqual(result.status, "succeeded")
            sql = client.requests[0][0].lower()
            self.assertIn("government", sql)
            self.assertIn("inflation", sql)
            self.assertIn("war", sql)
            self.assertIn("semiconductor", sql)

    def test_bad_topic_category_writes_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "gdelt_news_task_bad", "bundle": "gdelt_news", "params": {"topic_categories": ["sports"]}, "output_root": str(Path(tmp) / "task")}
            result = run(task_key, run_id="run", client=FakeBigQueryClient([]))
            self.assertEqual(result.status, "failed")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["error"]["type"], "GdeltNewsError")


if __name__ == "__main__":
    unittest.main()
