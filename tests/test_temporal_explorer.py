import csv
import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from data_runtime.temporal_explorer import (
    CHART_OHLCV_CACHE_TABLE,
    OhlcvInputRow,
    aggregate_ohlcv_rows,
    build_calendar_day_rows,
    build_market_session_rows,
    official_exchange_market_session_rows,
    temporal_table_ddls,
)


class TemporalExplorerTests(unittest.TestCase):
    def test_builds_calendar_day_spine_flags(self):
        rows = build_calendar_day_rows("2026-03-31", "2026-04-02")
        self.assertEqual([row["calendar_date"] for row in rows], [date(2026, 3, 31), date(2026, 4, 1)])
        self.assertTrue(rows[0]["is_month_end"])
        self.assertTrue(rows[0]["is_quarter_end"])
        self.assertTrue(rows[1]["is_month_start"])
        self.assertTrue(rows[1]["is_quarter_start"])

    def test_market_sessions_include_equity_holiday_and_crypto_continuous(self):
        rows = build_market_session_rows("2026-01-01", "2026-01-03")
        by_key = {(row["venue"], row["calendar_date"]): row for row in rows}
        self.assertEqual(by_key[("NYSE", date(2026, 1, 1))]["session_type"], "closed")
        self.assertEqual(by_key[("NYSE", date(2026, 1, 1))]["holiday_name"], "New Year's Day")
        self.assertEqual(by_key[("NYSE", date(2026, 1, 2))]["session_type"], "regular")
        self.assertEqual(by_key[("CRYPTO_24_7", date(2026, 1, 1))]["session_type"], "crypto_continuous")

    def test_official_exchange_rows_override_with_early_close(self):
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "official_exchange_calendar.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["venue", "calendar_date", "session_status", "open_time", "close_time", "holiday_name", "source_ref"])
                writer.writeheader()
                writer.writerow(
                    {
                        "venue": "NYSE",
                        "calendar_date": "2026-11-27",
                        "session_status": "early_close",
                        "open_time": "2026-11-27T09:30:00-05:00",
                        "close_time": "2026-11-27T13:00:00-05:00",
                        "holiday_name": "Day after Thanksgiving",
                        "source_ref": "https://www.nyse.com/trade/hours-calendars",
                    }
                )
            rows = official_exchange_market_session_rows([path])
        self.assertEqual(rows[0]["session_type"], "early_close")
        self.assertEqual(rows[0]["source_priority"], "official_exchange_calendar")
        self.assertEqual(rows[0]["close_time"], datetime(2026, 11, 27, 18, 0, tzinfo=UTC))

    def test_chart_cache_ddl_is_registered(self):
        ddl = "\n".join(temporal_table_ddls())
        self.assertIn(CHART_OHLCV_CACHE_TABLE, ddl)
        self.assertNotIn("calendar_scheduled_event", ddl)
        self.assertNotIn("calendar_event_result", ddl)
        self.assertNotIn("calendar_news_event_index", ddl)

    def test_aggregates_ohlcv_rows(self):
        rows = [
            OhlcvInputRow("SPY", datetime(2026, 5, 1, 13, 30, tzinfo=UTC), 100, 101, 99, 100.5, 10, 100.4, "m01_market_regime_data_acquisition"),
            OhlcvInputRow("SPY", datetime(2026, 5, 1, 13, 40, tzinfo=UTC), 100.5, 103, 100, 102, 30, 101.5, "m01_market_regime_data_acquisition"),
        ]
        buckets = aggregate_ohlcv_rows(rows, "30min")
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0]["open"], 100)
        self.assertEqual(buckets[0]["high"], 103)
        self.assertEqual(buckets[0]["low"], 99)
        self.assertEqual(buckets[0]["close"], 102)
        self.assertEqual(buckets[0]["bar_count"], 2)


if __name__ == "__main__":
    unittest.main()
