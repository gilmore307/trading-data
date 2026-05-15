from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from importlib import import_module


extract_events_from_artifact_paths = import_module(
    "data_source.source_04_event_overlay.feed_event_extraction"
).extract_events_from_artifact_paths
source_pipeline = import_module("data_source.source_04_event_overlay.pipeline")


class FakeSqlWriter:
    def __init__(self) -> None:
        self.calls = []

    def write_rows(self, *, table, columns, rows, key_columns):
        self.calls.append({"table": table, "columns": columns, "rows": rows, "key_columns": key_columns})
        return {"table": table, "qualified_table": f"trading_data.{table}", "row_count": len(rows)}


class EventOverlayFeedExtractionTests(unittest.TestCase):
    def test_extracts_news_sec_macro_artifacts_to_canonical_event_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            alpaca = tmp / "equity_news.csv"
            with alpaca.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id", "timeline_headline", "created_at", "updated_at", "symbols", "summary", "event_link_url"])
                writer.writeheader()
                writer.writerow({"id": "n1", "timeline_headline": "Apple reports results", "created_at": "2024-01-09T14:46:19-05:00", "updated_at": "2024-01-09T14:47:00-05:00", "symbols": "['AAPL']", "summary": "Earnings article", "event_link_url": "https://example.com/aapl"})
            gdelt = tmp / "gdelt_article.csv"
            with gdelt.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["article_id", "seen_at", "source_domain", "event_link_url", "title", "source_theme_tags", "organizations", "tone", "impact_scope"])
                writer.writeheader()
                writer.writerow({"article_id": "g1", "seen_at": "2024-01-09T09:00:00-05:00", "source_domain": "reuters.com", "event_link_url": "https://example.com/macro", "title": "Fed policy update", "source_theme_tags": "ECON_STOCKMARKET", "organizations": "Federal Reserve", "tone": "-1.0", "impact_scope": "market"})
            te = tmp / "trading_economics_calendar_event.csv"
            with te.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["event_time", "country", "event", "source_event_type", "reference", "actual", "previous", "consensus", "te_forecast", "revised", "importance", "symbol", "source_url"])
                writer.writeheader()
                writer.writerow({"event_time": "2024-01-05T08:30:00-05:00", "country": "United States", "event": "Non Farm Payrolls", "actual": "216K", "previous": "173K", "consensus": "170K", "importance": "3", "source_url": "https://tradingeconomics.com/united-states/calendar"})
            sec = tmp / "sec_company_fact.csv"
            with sec.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["cik", "entity_name", "taxonomy", "tag", "label", "description", "unit", "fy", "fp", "form", "filed", "frame", "end", "value", "accession_number", "symbol"])
                writer.writeheader()
                writer.writerow({"cik": "320193", "entity_name": "Apple Inc.", "taxonomy": "us-gaap", "tag": "Revenues", "unit": "USD", "fy": "2024", "fp": "Q1", "form": "10-Q", "filed": "2024-02-02", "end": "2023-12-30", "value": "119575000000", "accession_number": "0000320193-24-000006", "symbol": "AAPL"})
                writer.writerow({"cik": "320193", "entity_name": "Apple Inc.", "taxonomy": "us-gaap", "tag": "NetIncomeLoss", "unit": "USD", "fy": "2024", "fp": "Q1", "form": "10-Q", "filed": "2024-02-02", "end": "2023-12-30", "value": "33916000000", "accession_number": "0000320193-24-000006", "symbol": "AAPL"})

            rows = extract_events_from_artifact_paths([alpaca, gdelt, te, sec])
            categories = {row["event_category_type"] for row in rows}
            self.assertEqual(categories, {"symbol_news", "macro_news", "macro_data", "earnings_guidance"})
            self.assertEqual({row["source_name"] for row in rows}, {"03_feed_alpaca_news", "05_feed_gdelt_news", "07_feed_trading_economics_calendar_web", "08_feed_sec_company_financials"})
            sec_rows = [row for row in rows if row["event_category_type"] == "earnings_guidance" and row["source_name"] == "08_feed_sec_company_financials"]
            self.assertEqual(len(sec_rows), 1)
            self.assertIn("grouped_rows=2", sec_rows[0]["summary"])
            self.assertIn("event_phase=release_result", sec_rows[0]["summary"])
            self.assertEqual([row for row in rows if row.get("symbol") == "AAPL"][0]["scope_type"], "symbol")


    def test_extracts_nasdaq_earnings_calendar_as_scheduled_shell(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            calendar = tmp / "release_calendar.csv"
            with calendar.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["event_id", "calendar_source", "event_name", "release_time", "event_date", "timezone", "source_url", "raw_summary"])
                writer.writeheader()
                writer.writerow({
                    "event_id": "cal1",
                    "calendar_source": "nasdaq_earnings_calendar",
                    "event_name": "AAPL earnings release (Apple Inc.)",
                    "release_time": "2026-04-24T08:00:00-04:00",
                    "event_date": "2026-04-24",
                    "timezone": "America/New_York",
                    "source_url": "https://api.nasdaq.com/api/calendar/earnings?date=2026-04-24",
                    "raw_summary": "{\"time\": \"time-pre-market\"}",
                })

            rows = extract_events_from_artifact_paths([calendar])
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["event_category_type"], "earnings_guidance")
            self.assertEqual(row["information_role_type"], "prior_signal")
            self.assertEqual(row["source_priority"], "approved_calendar")
            self.assertEqual(row["symbol"], "AAPL")
            self.assertIn("event_phase=scheduled_shell", row["summary"])
            self.assertIn("result_fields=not_available_from_calendar_shell", row["summary"])

    def test_source_pipeline_accepts_event_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            alpaca = tmp / "equity_news.csv"
            with alpaca.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id", "timeline_headline", "created_at", "updated_at", "symbols", "summary", "event_link_url"])
                writer.writeheader()
                writer.writerow({"id": "n1", "timeline_headline": "Apple files earnings story", "created_at": "2024-01-09T14:46:19-05:00", "updated_at": "2024-01-09T14:47:00-05:00", "symbols": "AAPL", "summary": "Article", "event_link_url": "https://example.com/aapl"})
            task_key = {
                "task_id": "source_04_event_overlay_artifact_task",
                "source": "source_04_event_overlay",
                "params": {"start": "2024-01-01T00:00:00-05:00", "end": "2024-02-01T00:00:00-05:00", "event_artifact_paths": [str(alpaca)]},
                "output_root": str(tmp / "task"),
            }
            writer = FakeSqlWriter()
            result = source_pipeline.run(task_key, run_id="run", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["source_04_event_overlay"], 1)
            row = writer.calls[0]["rows"][0]
            self.assertEqual(row["event_category_type"], "symbol_news")
            self.assertEqual(row["source_name"], "03_feed_alpaca_news")

    def test_source_pipeline_preserves_same_time_macro_calendar_events(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            te = tmp / "trading_economics_calendar_event.csv"
            with te.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["event_time", "country", "event", "source_event_type", "reference", "actual", "previous", "consensus", "te_forecast", "revised", "importance", "symbol", "source_url"])
                writer.writeheader()
                writer.writerow({"event_time": "2024-01-20T08:30:00-05:00", "country": "United States", "event": "Core Inflation Rate YoY", "actual": "2.1%", "importance": "3", "source_url": "https://tradingeconomics.com/united-states/calendar"})
                writer.writerow({"event_time": "2024-01-20T08:30:00-05:00", "country": "United States", "event": "Inflation Rate YoY", "actual": "0.7%", "importance": "3", "source_url": "https://tradingeconomics.com/united-states/calendar"})
            task_key = {
                "task_id": "source_04_event_overlay_same_time_macro_task",
                "source": "source_04_event_overlay",
                "params": {"start": "2024-01-01T00:00:00-05:00", "end": "2024-02-01T00:00:00-05:00", "event_artifact_paths": [str(te)]},
                "output_root": str(tmp / "task"),
            }
            writer = FakeSqlWriter()
            result = source_pipeline.run(task_key, run_id="run", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["source_04_event_overlay"], 2)
            rows = writer.calls[0]["rows"]
            self.assertEqual({row["title"] for row in rows}, {"Core Inflation Rate YoY", "Inflation Rate YoY"})
            self.assertEqual(len({row["event_id"] for row in rows}), 2)

    def test_source_pipeline_skips_feed_events_outside_requested_window(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            te = tmp / "trading_economics_calendar_event.csv"
            with te.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["event_time", "country", "event", "source_event_type", "reference", "actual", "previous", "consensus", "te_forecast", "revised", "importance", "symbol", "source_url"])
                writer.writeheader()
                writer.writerow({"event_time": "Thursday May 14 2026", "country": "United States", "event": "Current-page row", "importance": "3", "source_url": "https://tradingeconomics.com/united-states/calendar"})
                writer.writerow({"event_time": "2024-01-05T08:30:00-05:00", "country": "United States", "event": "Non Farm Payrolls", "actual": "216K", "importance": "3", "source_url": "https://tradingeconomics.com/united-states/calendar"})
            task_key = {
                "task_id": "source_04_event_overlay_artifact_task",
                "source": "source_04_event_overlay",
                "params": {"start": "2024-01-01T00:00:00-05:00", "end": "2024-02-01T00:00:00-05:00", "event_artifact_paths": [str(te)]},
                "output_root": str(tmp / "task"),
            }
            writer = FakeSqlWriter()
            result = source_pipeline.run(task_key, run_id="run", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["source_04_event_overlay"], 1)
            self.assertIn("out_of_window_event_rows_skipped=1", result.warnings)
            self.assertEqual(writer.calls[0]["rows"][0]["event_category_type"], "macro_data")


if __name__ == "__main__":
    unittest.main()
