import importlib
import unittest


class FakeCursor:
    def __init__(self):
        self.calls = []
        self._one = {"table_ref": "fixture.table"}

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self._one

    def fetchall(self):
        return []


class FeatureSqlWindowTests(unittest.TestCase):
    def test_market_regime_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.m01_market_regime_feature_generation.sql")
        cursor = FakeCursor()
        module.fetch_source_bars(
            cursor,
            source_schema="trading_data",
            source_table="model_01_market_regime_data_acquisition",
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
            source_table="model_01_market_regime_data_acquisition",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("timestamp < %s", sql)
        self.assertNotIn("timestamp <= %s", sql)
        self.assertEqual(params, ["2026-05-01T00:00:00Z"])

    def test_target_state_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.m03_target_state_vector_feature_generation.sql")
        cursor = FakeCursor()
        module.fetch_source_rows(
            cursor,
            source_schema="trading_data",
            source_table="model_03_target_state_vector_data_acquisition",
            source_start="2026-04-01T00:00:00Z",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("available_time >= %s", sql)
        self.assertIn("available_time < %s", sql)
        self.assertNotIn("available_time <= %s", sql)
        self.assertEqual(params, ["2026-04-01T00:00:00Z", "2026-05-01T00:00:00Z"])

    def test_target_state_context_keeps_prior_point_in_time_rows(self):
        module = importlib.import_module("data_feature.m03_target_state_vector_feature_generation.sql")
        cursor = FakeCursor()
        module.fetch_context_rows(
            cursor,
            schema="trading_data",
            table="model_01_market_regime_feature_generation",
            ref_column="market_context_state_ref",
            source_start="2026-04-01T09:30:00Z",
            source_end="2026-04-01T16:00:00Z",
        )
        sql, params = cursor.calls[-1]
        self.assertNotIn("available_time >= %s", sql)
        self.assertIn("available_time < %s", sql)
        self.assertNotIn("available_time <= %s", sql)
        self.assertEqual(params, ["2026-04-01T16:00:00Z"])

    def test_event_state_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.m03_event_state_feature_generation.sql")
        cursor = FakeCursor()
        module.fetch_source_rows(
            cursor,
            source_schema="trading_data",
            source_table="model_03_event_state_data_acquisition",
            source_end="2026-05-01T00:00:00Z",
        )
        sql, params = cursor.calls[0]
        self.assertIn("available_time < %s", sql)
        self.assertNotIn("available_time <= %s", sql)
        self.assertEqual(params, ["2026-05-01T00:00:00Z"])

    def test_option_expression_source_end_is_half_open(self):
        module = importlib.import_module("data_feature.m05_option_expression_feature_generation.sql")
        cursor = FakeCursor()
        module.fetch_source_rows(
            cursor,
            source_schema="trading_data",
            source_table="option_chain_state_source",
            source_start="2026-04-01T00:00:00Z",
            source_end="2026-05-01T00:00:00Z",
            underlying="AAPL",
        )
        sql, params = cursor.calls[0]
        self.assertIn("underlying = %s", sql)
        self.assertIn("snapshot_time >= %s", sql)
        self.assertIn("snapshot_time < %s", sql)
        self.assertNotIn("snapshot_time <= %s", sql)
        self.assertEqual(params, ["AAPL", "2026-04-01T00:00:00Z", "2026-05-01T00:00:00Z"])

    def test_option_expression_generation_uses_set_based_insert(self):
        module = importlib.import_module("data_feature.m05_option_expression_feature_generation.sql")
        cursor = FakeCursor()
        module.insert_feature_rows_from_source_sql(
            cursor,
            source_schema="trading_data",
            source_table="option_chain_state_source",
            target_schema="trading_data",
            target_table="model_05_option_expression_feature_generation",
            source_start="2026-04-01T00:00:00Z",
            source_end="2026-05-01T00:00:00Z",
            underlying="AAPL",
            run_id="unit_run",
        )
        statements = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn("INSERT INTO", statements)
        self.assertIn("SELECT", statements)
        self.assertIn("ON CONFLICT", statements)
        self.assertIn("IS DISTINCT FROM EXCLUDED", statements)
        self.assertIn("underlying_price = 0", statements)
        self.assertIn("NULLIF(bid_size + ask_size, 0)", statements)
        self.assertIn("NULLIF(feature_mid, 0)", statements)
        self.assertNotIn('"run_id" = EXCLUDED."run_id"', statements)
        self.assertIn("underlying = %s", statements)
        self.assertNotIn("snapshot_time <= %s", statements)
        self.assertEqual(cursor.calls[-1][1], ["AAPL", "2026-04-01T00:00:00Z", "2026-05-01T00:00:00Z", "unit_run"])


if __name__ == "__main__":
    unittest.main()
