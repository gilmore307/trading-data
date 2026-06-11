from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from importlib import import_module


extract_events_from_artifact_paths = import_module(
    "data_source.m06_residual_event_governance_data_acquisition.feed_event_extraction"
).extract_events_from_artifact_paths
extract_events_from_sql_inputs = import_module(
    "data_source.m06_residual_event_governance_data_acquisition.feed_event_extraction"
).extract_events_from_sql_inputs
source_pipeline = import_module("data_source.m06_residual_event_governance_data_acquisition.pipeline")


class FakeSqlWriter:
    def __init__(self) -> None:
        self.calls = []

    def write_rows(self, *, table, columns, rows, key_columns):
        self.calls.append({"table": table, "columns": columns, "rows": rows, "key_columns": key_columns})
        return {"table": table, "qualified_table": f"trading_data.{table}", "row_count": len(rows)}


class FakeSqlReader:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.calls = []

    def read_rows(self, *, table, columns, where_equals=None, where_in=None, time_column=None, start=None, end=None, order_by=None):
        self.calls.append({"table": table, "columns": columns, "where_equals": where_equals, "where_in": where_in, "time_column": time_column, "start": start, "end": end, "order_by": order_by})
        return [{column: row.get(column) for column in columns} for row in self.rows_by_table.get(table, [])]


class EventOverlayFeedExtractionTests(unittest.TestCase):
    def test_extracts_news_and_sec_artifacts_to_canonical_event_rows(self) -> None:
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
            sec = tmp / "sec_company_fact.csv"
            with sec.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["cik", "entity_name", "taxonomy", "tag", "label", "description", "unit", "fy", "fp", "form", "filed", "frame", "end", "value", "accession_number", "symbol"])
                writer.writeheader()
                writer.writerow({"cik": "320193", "entity_name": "Apple Inc.", "taxonomy": "us-gaap", "tag": "Revenues", "unit": "USD", "fy": "2024", "fp": "Q1", "form": "10-Q", "filed": "2024-02-02", "end": "2023-12-30", "value": "119575000000", "accession_number": "0000320193-24-000006", "symbol": "AAPL"})
                writer.writerow({"cik": "320193", "entity_name": "Apple Inc.", "taxonomy": "us-gaap", "tag": "NetIncomeLoss", "unit": "USD", "fy": "2024", "fp": "Q1", "form": "10-Q", "filed": "2024-02-02", "end": "2023-12-30", "value": "33916000000", "accession_number": "0000320193-24-000006", "symbol": "AAPL"})

            rows = extract_events_from_artifact_paths([alpaca, gdelt, sec])
            categories = {row["event_category_type"] for row in rows}
            self.assertEqual(categories, {"symbol_news", "macro_news", "earnings_guidance"})
            self.assertEqual({row["source_name"] for row in rows}, {"03_feed_alpaca_news", "05_feed_gdelt_news", "08_feed_sec_company_financials"})
            sec_rows = [row for row in rows if row["event_category_type"] == "earnings_guidance" and row["source_name"] == "08_feed_sec_company_financials"]
            self.assertEqual(len(sec_rows), 1)
            self.assertIn("grouped_rows=2", sec_rows[0]["summary"])
            self.assertIn("event_phase=release_result", sec_rows[0]["summary"])
            self.assertEqual([row for row in rows if row.get("symbol") == "AAPL"][0]["scope_type"], "symbol")

    def test_extracts_sql_feed_rows_to_canonical_event_rows(self) -> None:
        reader = FakeSqlReader(
            {
                "feed_03_alpaca_news": [
                    {"id": "n1", "timeline_headline": "Apple reports results", "created_at": "2024-01-09T14:46:19-05:00", "updated_at": "2024-01-09T14:47:00-05:00", "symbols": "AAPL", "summary": "Earnings article", "event_link_url": "https://example.com/aapl"}
                ],
                "feed_05_gdelt_article": [
                    {"article_id": "g1", "seen_at": "2024-01-09T09:00:00-05:00", "source_domain": "reuters.com", "event_link_url": "https://example.com/macro", "title": "Fed policy update", "source_theme_tags": "ECON_STOCKMARKET", "organizations": "Federal Reserve", "tone": "-1.0", "impact_scope": "market"}
                ],
                "feed_08_sec_company_fact": [
                    {"cik": "320193", "entity_name": "Apple Inc.", "taxonomy": "us-gaap", "tag": "Revenues", "unit": "USD", "fy": "2024", "fp": "Q1", "form": "10-Q", "filed": "2024-02-02", "end": "2023-12-30", "value": "119575000000", "accession_number": "0000320193-24-000006", "symbol": "AAPL"}
                ],
                "feed_12_release_calendar": [
                    {"event_id": "cal1", "calendar_source": "nasdaq_earnings_calendar", "event_name": "AAPL earnings release (Apple Inc.)", "release_time": "2026-04-24T08:00:00-04:00", "event_date": "2026-04-24", "timezone": "America/New_York", "source_url": "https://api.nasdaq.com/api/calendar/earnings?date=2026-04-24", "raw_summary": "{}"}
                ],
            }
        )
        rows = extract_events_from_sql_inputs(
            [
                {"table": "feed_03_alpaca_news"},
                {"table": "feed_05_gdelt_article"},
                {"table": "feed_08_sec_company_fact"},
                {"table": "feed_12_release_calendar"},
            ],
            sql_reader=reader,
        )
        self.assertEqual({row["event_category_type"] for row in rows}, {"symbol_news", "macro_news", "earnings_guidance"})
        self.assertTrue(all(row["source_artifact_path"].startswith("sql://trading_data/feed_") for row in rows))
        self.assertEqual([call["table"] for call in reader.calls], ["feed_03_alpaca_news", "feed_05_gdelt_article", "feed_08_sec_company_fact", "feed_12_release_calendar"])


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

    def test_trading_economics_calendar_artifact_is_not_layer_ten_input(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            te = tmp / "trading_economics_calendar_event.csv"
            with te.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["event_time", "country", "event", "source_event_type", "reference", "actual", "previous", "consensus", "te_forecast", "revised", "importance", "symbol"])
                writer.writeheader()
                writer.writerow({"event_time": "2026-05-28T08:30:00-04:00", "country": "United States", "event": "GDP Growth Rate QoQ", "consensus": "2.0%", "importance": "3"})

            with self.assertRaisesRegex(Exception, "unsupported event feed artifact shape"):
                extract_events_from_artifact_paths([te])

    def test_source_pipeline_accepts_event_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            alpaca = tmp / "equity_news.csv"
            with alpaca.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id", "timeline_headline", "created_at", "updated_at", "symbols", "summary", "event_link_url"])
                writer.writeheader()
                writer.writerow({"id": "n1", "timeline_headline": "Apple files earnings story", "created_at": "2024-01-09T14:46:19-05:00", "updated_at": "2024-01-09T14:47:00-05:00", "symbols": "AAPL", "summary": "Article", "event_link_url": "https://example.com/aapl"})
            task_key = {
                "task_id": "m06_residual_event_governance_data_acquisition_artifact_task",
                "source": "m06_residual_event_governance_data_acquisition",
                "params": {"start": "2024-01-01T00:00:00-05:00", "end": "2024-02-01T00:00:00-05:00", "event_artifact_paths": [str(alpaca)]},
                "output_root": str(tmp / "task"),
            }
            writer = FakeSqlWriter()
            result = source_pipeline.run(task_key, run_id="run", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["m06_residual_event_governance_data_acquisition"], 1)
            row = writer.calls[0]["rows"][0]
            self.assertEqual(row["event_category_type"], "symbol_news")
            self.assertEqual(row["source_name"], "03_feed_alpaca_news")
            self.assertEqual(row["source_artifact_path"], str(alpaca))

    def test_source_pipeline_accepts_event_sql_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            task_key = {
                "task_id": "m06_residual_event_governance_data_acquisition_sql_task",
                "source": "m06_residual_event_governance_data_acquisition",
                "params": {
                    "start": "2024-01-01T00:00:00-05:00",
                    "end": "2024-02-01T00:00:00-05:00",
                    "event_sql_inputs": [{"table": "feed_03_alpaca_news"}],
                },
                "output_root": str(tmp / "task"),
            }
            writer = FakeSqlWriter()
            reader = FakeSqlReader({"feed_03_alpaca_news": [{"id": "n1", "timeline_headline": "Apple files earnings story", "created_at": "2024-01-09T14:46:19-05:00", "updated_at": "2024-01-09T14:47:00-05:00", "symbols": "AAPL", "summary": "Article", "event_link_url": "https://example.com/aapl"}]})
            result = source_pipeline.run(task_key, run_id="run", sql_writer=writer, sql_reader=reader)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["m06_residual_event_governance_data_acquisition"], 1)
            row = writer.calls[0]["rows"][0]
            self.assertEqual(row["event_category_type"], "symbol_news")
            self.assertEqual(row["source_artifact_path"], "sql://trading_data/feed_03_alpaca_news")

    def test_source_pipeline_preserves_same_time_news_events(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            gdelt = tmp / "gdelt_article.csv"
            with gdelt.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["article_id", "seen_at", "source_domain", "event_link_url", "title", "source_theme_tags", "organizations", "tone", "impact_scope"])
                writer.writeheader()
                writer.writerow({"article_id": "g1", "seen_at": "2024-01-20T08:30:00-05:00", "source_domain": "reuters.com", "event_link_url": "https://example.com/1", "title": "Fed rate story", "source_theme_tags": "ECON", "organizations": "Federal Reserve", "tone": "-1", "impact_scope": "market"})
                writer.writerow({"article_id": "g2", "seen_at": "2024-01-20T08:30:00-05:00", "source_domain": "reuters.com", "event_link_url": "https://example.com/2", "title": "Inflation story", "source_theme_tags": "ECON", "organizations": "BLS", "tone": "-2", "impact_scope": "market"})
            task_key = {
                "task_id": "m06_residual_event_governance_data_acquisition_same_time_macro_task",
                "source": "m06_residual_event_governance_data_acquisition",
                "params": {"start": "2024-01-01T00:00:00-05:00", "end": "2024-02-01T00:00:00-05:00", "event_artifact_paths": [str(gdelt)]},
                "output_root": str(tmp / "task"),
            }
            writer = FakeSqlWriter()
            result = source_pipeline.run(task_key, run_id="run", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["m06_residual_event_governance_data_acquisition"], 2)
            rows = writer.calls[0]["rows"]
            self.assertEqual({row["title"] for row in rows}, {"Fed rate story", "Inflation story"})
            self.assertEqual(len({row["event_id"] for row in rows}), 2)

    def test_source_pipeline_skips_feed_events_outside_requested_window(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            gdelt = tmp / "gdelt_article.csv"
            with gdelt.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["article_id", "seen_at", "source_domain", "event_link_url", "title", "source_theme_tags", "organizations", "tone", "impact_scope"])
                writer.writeheader()
                writer.writerow({"article_id": "g1", "seen_at": "2026-05-14T08:30:00-04:00", "source_domain": "reuters.com", "event_link_url": "https://example.com/out", "title": "Out of window", "source_theme_tags": "ECON", "organizations": "Fed", "tone": "-1", "impact_scope": "market"})
                writer.writerow({"article_id": "g2", "seen_at": "2024-01-05T08:30:00-05:00", "source_domain": "reuters.com", "event_link_url": "https://example.com/in", "title": "In window", "source_theme_tags": "ECON", "organizations": "Fed", "tone": "-1", "impact_scope": "market"})
            task_key = {
                "task_id": "m06_residual_event_governance_data_acquisition_artifact_task",
                "source": "m06_residual_event_governance_data_acquisition",
                "params": {"start": "2024-01-01T00:00:00-05:00", "end": "2024-02-01T00:00:00-05:00", "event_artifact_paths": [str(gdelt)]},
                "output_root": str(tmp / "task"),
            }
            writer = FakeSqlWriter()
            result = source_pipeline.run(task_key, run_id="run", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["m06_residual_event_governance_data_acquisition"], 1)
            self.assertIn("out_of_window_event_rows_skipped=1", result.warnings)
            self.assertEqual(writer.calls[0]["rows"][0]["event_category_type"], "macro_news")


if __name__ == "__main__":
    unittest.main()
