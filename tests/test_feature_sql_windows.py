import importlib
import unittest


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return []


class FeatureSqlWindowTests(unittest.TestCase):
    def test_market_regime_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.m01_market_regime_feature_generation.sql")
        cursor = FakeCursor()
        module.fetch_source_bars(
            cursor,
            source_schema="trading_data",
            source_table="m01_market_regime_data_acquisition",
            source_start="2026-04-01T00:00:00Z",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("timestamp >= %s", sql)
        self.assertIn("timestamp < %s", sql)
        self.assertNotIn("timestamp <= %s", sql)
        self.assertEqual(params, ["2026-04-01T00:00:00Z", "2026-05-01T00:00:00Z"])

    def test_sector_context_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.m02_sector_context_feature_generation.sql")
        cursor = FakeCursor()
        module.fetch_source_bars(
            cursor,
            source_schema="trading_data",
            source_table="m01_market_regime_data_acquisition",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("timestamp < %s", sql)
        self.assertNotIn("timestamp <= %s", sql)
        self.assertEqual(params, ["2026-05-01T00:00:00Z"])

    def test_target_state_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.feature_03_target_state_vector.sql")
        cursor = FakeCursor()
        module.fetch_source_rows(
            cursor,
            source_schema="trading_data",
            source_table="source_03_target_state",
            source_start="2026-04-01T00:00:00Z",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("available_time >= %s", sql)
        self.assertIn("available_time < %s", sql)
        self.assertNotIn("available_time <= %s", sql)
        self.assertEqual(params, ["2026-04-01T00:00:00Z", "2026-05-01T00:00:00Z"])

    def test_target_state_context_keeps_prior_point_in_time_rows(self):
        module = importlib.import_module("data_feature.feature_03_target_state_vector.sql")
        cursor = FakeCursor()
        module.fetch_context_rows(
            cursor,
            schema="trading_data",
            table="m01_market_regime_feature_generation",
            ref_column="market_context_state_ref",
            source_start="2026-04-01T09:30:00Z",
            source_end="2026-04-01T16:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertNotIn("available_time >= %s", sql)
        self.assertIn("available_time < %s", sql)
        self.assertNotIn("available_time <= %s", sql)
        self.assertEqual(params, ["2026-04-01T16:00:00Z"])

    def test_event_risk_governor_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.feature_10_event_risk_governor.sql")
        cursor = FakeCursor()
        module.fetch_source_rows(
            cursor,
            source_schema="trading_data",
            source_table="m10_event_risk_governor_data_acquisition",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("available_time < %s", sql)
        self.assertNotIn("available_time <= %s", sql)
        self.assertEqual(params, ["2026-05-01T00:00:00Z"])


if __name__ == "__main__":
    unittest.main()
