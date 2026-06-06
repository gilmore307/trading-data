from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from importlib import import_module
from tests.data_feed.fake_sql import FakeSqlWriter

run = import_module("data_feed.05_feed_gdelt_news.pipeline").run


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
    def test_05_feed_gdelt_news_fetch_clean_save_receipt(self):
        rows = [
            {
                "article_id": "20260427123000-1",
                "gdelt_date": "20260427123000",
                "source_domain": "example.com",
                "event_link_url": "https://example.com/politics-economy-tech",
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
                "task_id": "05_feed_gdelt_news_task_test",
                "feed": "05_feed_gdelt_news",
                "params": {"query_terms": ["inflation", "semiconductor"], "start_date": "2026-04-27", "end_date": "2026-04-28", "max_rows": 10},
                "output_root": str(Path(tmp) / "05_feed_gdelt_news_task_test"),
            }
            client = FakeBigQueryClient(rows)
            writer = FakeSqlWriter()
            result = run(task_key, run_id="05_feed_gdelt_news_run_test", client=client, client_is_fixture=True, sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["gdelt_article"], 1)
            sql, max_results, maximum_bytes_billed, dry_run = client.requests[0]
            self.assertIn("gdelt-bq.gdeltv2.gkg_partitioned", sql)
            self.assertIn("date(_partitiontime) >= date('2026-04-27')", sql.lower())
            self.assertIn("date(_partitiontime) < date('2026-04-28')", sql.lower())
            self.assertIn("united states", sql.lower())
            self.assertIn("reuters.com", sql.lower())
            self.assertEqual(max_results, 10)
            self.assertIsNone(maximum_bytes_billed)
            self.assertFalse(dry_run)
            row = writer.rows_for("feed_05_gdelt_article")[0]
            self.assertEqual(row["article_id"], "20260427123000-1")
            self.assertEqual(row["seen_at"], "2026-04-27T08:30:00-04:00")
            self.assertEqual(row["tone"], "-1.2")
            run_dir = Path(task_key["output_root"]) / "runs" / "05_feed_gdelt_news_run_test"
            self.assertFalse((run_dir / "saved/gdelt_article.csv").exists())
            self.assertFalse((run_dir / "cleaned/gdelt_article.jsonl").exists())
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["row_counts"]["gdelt_article"], 1)

    def test_default_topics_allow_omitting_query_terms(self):
        rows = [{"article_id": "a", "gdelt_date": "20260427123000", "source_domain": "reuters.com", "event_link_url": "https://reuters.com/a"}]
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "05_feed_gdelt_news_task_default", "feed": "05_feed_gdelt_news", "params": {"max_rows": 1, "start_date": "2026-04-27", "end_date": "2026-04-28"}, "output_root": str(Path(tmp) / "task")}
            client = FakeBigQueryClient(rows)
            result = run(task_key, run_id="run", client=client, client_is_fixture=True, sql_writer=FakeSqlWriter())
            self.assertEqual(result.status, "succeeded")
            sql = client.requests[0][0].lower()
            self.assertIn("government", sql)
            self.assertIn("inflation", sql)
            self.assertIn("war", sql)
            self.assertIn("semiconductor", sql)

    def test_out_of_window_rows_are_skipped(self):
        rows = [
            {"article_id": "inside", "gdelt_date": "20260427123000", "source_domain": "reuters.com", "event_link_url": "https://reuters.com/inside"},
            {"article_id": "outside", "gdelt_date": "20260428123000", "source_domain": "reuters.com", "event_link_url": "https://reuters.com/outside"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "05_feed_gdelt_news_task_window", "feed": "05_feed_gdelt_news", "params": {"query_terms": ["inflation"], "start_date": "2026-04-27", "end_date": "2026-04-28"}, "output_root": str(Path(tmp) / "task")}
            writer = FakeSqlWriter()
            result = run(task_key, run_id="run", client=FakeBigQueryClient(rows), client_is_fixture=True, sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["gdelt_article"], 1)
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["steps"]["clean"]["warnings"], ["out_of_window_gdelt_rows_skipped=1"])
            saved_rows = writer.rows_for("feed_05_gdelt_article")
            self.assertEqual([row["article_id"] for row in saved_rows], ["inside"])

    def test_bad_topic_category_writes_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {"task_id": "05_feed_gdelt_news_task_bad", "feed": "05_feed_gdelt_news", "params": {"topic_categories": ["sports"]}, "output_root": str(Path(tmp) / "task")}
            result = run(task_key, run_id="run", client=FakeBigQueryClient([]), client_is_fixture=True)
            self.assertEqual(result.status, "failed")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["error"]["type"], "GdeltNewsError")


if __name__ == "__main__":
    unittest.main()
