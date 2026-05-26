import unittest
from datetime import date

from data_runtime.exchange_calendar import is_regular_us_equity_session, next_regular_us_equity_open_after


class ExchangeCalendarTests(unittest.TestCase):
    def test_next_open_skips_weekend_with_dst_offset(self):
        self.assertEqual(next_regular_us_equity_open_after("2026-04-24"), "2026-04-27T09:30:00-04:00")

    def test_next_open_skips_us_equity_holiday(self):
        self.assertFalse(is_regular_us_equity_session(date(2026, 1, 1)))
        self.assertEqual(next_regular_us_equity_open_after("2025-12-31"), "2026-01-02T09:30:00-05:00")

    def test_observed_new_year_holiday_can_fall_in_prior_year(self):
        self.assertFalse(is_regular_us_equity_session(date(2021, 12, 31)))
        self.assertEqual(next_regular_us_equity_open_after("2021-12-30"), "2022-01-03T09:30:00-05:00")
        self.assertFalse(is_regular_us_equity_session(date(2027, 12, 31)))


if __name__ == "__main__":
    unittest.main()
