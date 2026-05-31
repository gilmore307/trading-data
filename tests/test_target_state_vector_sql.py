from __future__ import annotations

import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
sql = importlib.import_module("data_feature.feature_03_target_state_vector.sql")


class FakeCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object]]] = []
        self._one = {"table_ref": None}
        self._many = []

    def execute(self, statement: str, params=None) -> None:
        self.calls.append((statement, list(params or [])))

    def executemany(self, statement: str, params_seq) -> None:
        for params in params_seq:
            self.execute(statement, params)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


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
            "target_context_state_version": "target_context_state",
            "market_state_features": {"state_observation_windows": ["10min"]},
            "sector_state_features": {"state_observation_windows": ["10min"]},
            "target_state_features": {"target_direction_return_shape": {"return_10min": 0.01}},
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

    def test_candidate_rows_bind_direct_sector_or_holdings_sector_symbol(self) -> None:
        cursor = FakeCursor()

        sql.fetch_candidate_rows(
            cursor,
            source_schema="trading_data",
            source_table="source_03_target_state",
            sector_context_schema="trading_model",
            sector_context_table="model_02_sector_context",
            holdings_schema="trading_data",
            holdings_table="m02_sector_context_data_acquisition",
            source_start="2016-01-01",
            source_end="2016-02-01",
            target_context_mapping_path=None,
        )

        statements = "\n".join(statement for statement, _ in cursor.calls)
        self.assertIn('COALESCE(direct_l2."sector_or_industry_symbol", NULL::text, NULL::text)', statements)
        self.assertIn('l2."sector_or_industry_symbol" = s."symbol"', statements)
        self.assertIn('s."available_time" >= %s', statements)

        cursor = FakeCursor()
        cursor._one = {"table_ref": "trading_data.m02_sector_context_data_acquisition"}
        sql.fetch_candidate_rows(
            cursor,
            source_schema="trading_data",
            source_table="source_03_target_state",
            sector_context_schema="trading_model",
            sector_context_table="model_02_sector_context",
            holdings_schema="custom_data",
            holdings_table="custom_holdings",
            target_context_mapping_path=None,
        )

        statements = "\n".join(statement for statement, _ in cursor.calls)
        self.assertIn('"custom_data"."custom_holdings"', statements)
        self.assertIn('h."holding_symbol" = s."symbol"', statements)
        self.assertIn('COALESCE(direct_l2."sector_or_industry_symbol", NULL::text, h."etf_symbol")', statements)

    def test_candidate_rows_use_accepted_target_context_mapping_before_holdings(self) -> None:
        with TemporaryDirectory() as tmp:
            mapping_path = Path(tmp) / "layer_02_target_context_mapping.csv"
            mapping_path.write_text(
                "target_symbol,target_asset_class,spot_ref,layer2_context_symbol,layer2_mapping_method_type,"
                "listed_proxy_symbol,optionable_proxy_symbol,optionable_proxy_status,proxy_role_type,proxy_use,"
                "review_status,interpretation\n"
                "AAPL,equity_common,AAPL,XLK,primary_sector_context,,,,,,accepted,AAPL maps to XLK.\n"
                "MSFT,equity_common,MSFT,XLK,primary_sector_context,,,,,,deferred,Not accepted.\n",
                encoding="utf-8",
            )
            cursor = FakeCursor()
            cursor._one = {"table_ref": "trading_data.m02_sector_context_data_acquisition"}

            sql.fetch_candidate_rows(
                cursor,
                source_schema="trading_data",
                source_table="source_03_target_state",
                sector_context_schema="trading_model",
                sector_context_table="model_02_sector_context",
                holdings_schema="custom_data",
                holdings_table="custom_holdings",
                target_context_mapping_path=mapping_path,
            )

        statements = "\n".join(statement for statement, _ in cursor.calls)
        params = [param for _, call_params in cursor.calls for param in call_params]
        self.assertIn("WITH target_context_mapping", statements)
        self.assertIn("mapping_l2.layer2_context_symbol", statements)
        self.assertIn('COALESCE(direct_l2."sector_or_industry_symbol", mapping_l2.layer2_context_symbol, h."etf_symbol")', statements)
        self.assertIn("AAPL", params)
        self.assertIn("XLK", params)
        self.assertNotIn("MSFT", params)

    def test_context_rows_keep_prior_point_in_time_context_before_source_start(self) -> None:
        cursor = FakeCursor()

        sql.fetch_context_rows(
            cursor,
            schema="trading_model",
            table="model_01_market_regime",
            ref_column="market_context_state_ref",
            source_start="2016-01-04T09:30:00-05:00",
            source_end="2016-01-04T16:00:00-05:00",
        )

        statement, params = cursor.calls[0]
        self.assertNotIn("available_time >= %s", statement)
        self.assertIn("available_time < %s", statement)
        self.assertEqual(params, ["2016-01-04T16:00:00-05:00"])


if __name__ == "__main__":
    unittest.main()
