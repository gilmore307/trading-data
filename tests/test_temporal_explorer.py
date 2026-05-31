import unittest
from datetime import UTC, date, datetime

from data_runtime.temporal_explorer import (
    CHART_OHLCV_CACHE_TABLE,
    OhlcvInputRow,
    aggregate_ohlcv_rows,
    build_calendar_day_rows,
    build_market_session_rows,
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
