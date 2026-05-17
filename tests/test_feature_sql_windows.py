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
        module = importlib.import_module("data_feature.feature_01_market_regime.sql")
        cursor = FakeCursor()
        module.fetch_source_bars(
            cursor,
            source_schema="trading_data",
            source_table="source_01_market_regime",
            source_start="2026-04-01T00:00:00Z",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("timestamp >= %s", sql)
        self.assertIn("timestamp < %s", sql)
        self.assertNotIn("timestamp <= %s", sql)
        self.assertEqual(params, ["2026-04-01T00:00:00Z", "2026-05-01T00:00:00Z"])

    def test_sector_context_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.feature_02_sector_context.sql")
        cursor = FakeCursor()
        module.fetch_source_bars(
            cursor,
            source_schema="trading_data",
            source_table="source_01_market_regime",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("timestamp < %s", sql)
        self.assertNotIn("timestamp <= %s", sql)
        self.assertEqual(params, ["2026-05-01T00:00:00Z"])

    def test_target_state_source_and_context_end_are_half_open(self):
        module = importlib.import_module("data_feature.feature_03_target_state_vector.sql")
        for call in (module.fetch_source_rows, module.fetch_context_rows):
            cursor = FakeCursor()
            kwargs = {
                "source_start": "2026-04-01T00:00:00Z",
                "source_end": "2026-05-01T00:00:00Z",
            }
            if call is module.fetch_source_rows:
                call(cursor, source_schema="trading_data", source_table="source_03_target_state", **kwargs)
            else:
                call(cursor, schema="trading_data", table="feature_01_market_regime", ref_column="market_context_state_ref", **kwargs)
            sql, params = cursor.calls[0]
            self.assertIn("available_time >= %s", sql)
            self.assertIn("available_time < %s", sql)
            self.assertNotIn("available_time <= %s", sql)
            self.assertEqual(params, ["2026-04-01T00:00:00Z", "2026-05-01T00:00:00Z"])

    def test_event_risk_governor_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.feature_09_event_risk_governor.sql")
        cursor = FakeCursor()
        module.fetch_source_rows(
            cursor,
            source_schema="trading_data",
            source_table="source_09_event_risk_governor",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("available_time < %s", sql)
        self.assertNotIn("available_time <= %s", sql)
        self.assertEqual(params, ["2026-05-01T00:00:00Z"])


if __name__ == "__main__":
    unittest.main()
