from __future__ import annotations

import importlib
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
sql = importlib.import_module("data_feature.feature_03_target_state_vector.sql")


class FakeCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object]]] = []

    def execute(self, statement: str, params=None) -> None:
        self.calls.append((statement, list(params or [])))


class TargetStateVectorSqlTests(unittest.TestCase):
    def test_writes_jsonb_feature_blocks_with_candidate_time_version_key(self) -> None:
        cursor = FakeCursor()
        now = datetime(2026, 1, 2, 9, 30, tzinfo=ET).isoformat()
        row = {
            "run_id": "run_001",
            "source_run_ref": "run_001",
            "available_time": now,
            "tradeable_time": now,
            "target_candidate_id": "tcand_001",
            "market_context_state_ref": "mkt_001",
            "sector_context_state_ref": "sec_001",
            "target_context_state_version": "target_context_state_v1",
            "market_state_features": {"state_observation_windows": ["5min"]},
            "sector_state_features": {"state_observation_windows": ["5min"]},
            "target_state_features": {"target_direction_return_shape": {"return_5min": 0.01}},
            "cross_state_features": {"target_vs_sector_residual_direction": 0.02},
            "feature_quality_diagnostics": {"has_target_bar": True},
        }

        sql.write_feature_rows_sql(cursor, [row], target_schema="trading_data", target_table="feature_03_target_state_vector")

        statements = "\n".join(statement for statement, _ in cursor.calls)
        self.assertIn('CREATE TABLE IF NOT EXISTS "trading_data"."feature_03_target_state_vector"', statements)
        self.assertIn('PRIMARY KEY ("target_candidate_id", "available_time", "target_context_state_version")', statements)
        self.assertIn('"market_state_features" JSONB', statements)
        insert_calls = [call for call in cursor.calls if "INSERT INTO" in call[0]]
        self.assertEqual(len(insert_calls), 1)
        self.assertIn('%s::jsonb', insert_calls[0][0])
        self.assertIn('"target_candidate_id"', insert_calls[0][0])


if __name__ == "__main__":
    unittest.main()
