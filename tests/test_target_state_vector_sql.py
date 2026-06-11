from __future__ import annotations

import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
sql = importlib.import_module("data_feature.m03_target_state_vector_feature_generation.sql")


class FakeCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object]]] = []
        self._one = {"table_ref": None}
        self._many = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement: str, params=None) -> None:
        self.calls.append((statement, list(params or [])))

    def executemany(self, statement: str, params_seq) -> None:
        for params in params_seq:
            self.execute(statement, params)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self):
        return self._cursor

    def commit(self) -> None:
        return None


class FakePsycopg:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def connect(self, database_url: str, row_factory=None) -> FakeConnection:
        return FakeConnection(self._cursor)


class FakeGenerator:
    def build_inputs(self, **kwargs):
        return kwargs

    def iter_rows(self, inputs, *, run_id, target_context_state_version, emit_start_time=None, emit_end_time=None):
        available_time = (emit_start_time or datetime(2026, 1, 2, 9, 30, tzinfo=ET)).isoformat()
        return iter(
            [
                {
                    "run_id": run_id,
                    "source_run_ref": run_id,
                    "available_time": available_time,
                    "tradeable_time": available_time,
                    "target_candidate_id": "tcand_001",
                    "market_context_state_ref": None,
                    "sector_context_state_ref": None,
                    "target_context_state_version": target_context_state_version,
                    "market_state_features": {},
                    "sector_state_features": {},
                    "target_state_features": {},
                    "cross_state_features": {},
                    "feature_quality_diagnostics": {},
                }
            ]
        )


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

        sql.write_feature_rows_sql(cursor, [row], target_schema="trading_data", target_table="model_03_target_state_vector_feature_generation")

        statements = "\n".join(statement for statement, _ in cursor.calls)
        self.assertIn('CREATE TABLE IF NOT EXISTS "trading_data"."model_03_target_state_vector_feature_generation"', statements)
        self.assertIn('PRIMARY KEY ("target_candidate_id", "available_time", "target_context_state_version")', statements)
        self.assertIn('"market_state_features" JSONB', statements)
        insert_calls = [call for call in cursor.calls if "INSERT INTO" in call[0]]
        self.assertEqual(len(insert_calls), 1)
        self.assertIn('%s::jsonb', insert_calls[0][0])
        self.assertIn('"target_candidate_id"', insert_calls[0][0])

    def test_source_rows_with_lookback_limits_history_per_candidate(self) -> None:
        cursor = FakeCursor()

        sql.fetch_source_rows_with_lookback(
            cursor,
            source_schema="trading_data",
            source_table="model_03_target_state_vector_data_acquisition",
            history_start="2016-01-01T00:00:00-05:00",
            output_start="2016-02-01T00:00:00-05:00",
            output_end="2016-03-01T00:00:00-05:00",
            lookback_rows=10080,
        )

        statement, params = cursor.calls[-1]
        self.assertIn('PARTITION BY "target_candidate_id"', statement)
        self.assertIn("history_rank <= %s", statement)
        self.assertIn("UNION ALL", statement)
        self.assertEqual(
            params,
            [
                "2016-01-01T00:00:00-05:00",
                "2016-02-01T00:00:00-05:00",
                "2016-02-01T00:00:00-05:00",
                "2016-03-01T00:00:00-05:00",
                10080,
            ],
        )

    def test_candidate_rows_bind_direct_sector_or_null_sector_symbol(self) -> None:
        cursor = FakeCursor()
        cursor._one = {"table_ref": "trading_model.model_02_sector_context_model_generation"}

        sql.fetch_candidate_rows(
            cursor,
            source_schema="trading_data",
            source_table="model_03_target_state_vector_data_acquisition",
            sector_context_schema="trading_model",
            sector_context_table="m02_sector_context_model_generation",
            source_start="2016-01-01",
            source_end="2016-02-01",
            target_context_mapping_path=None,
        )

        statements = "\n".join(statement for statement, _ in cursor.calls)
        self.assertIn('COALESCE(direct_l2."sector_or_industry_symbol", NULL::text)', statements)
        self.assertIn('l2."sector_or_industry_symbol" = s."symbol"', statements)
        self.assertIn('s."available_time" >= %s', statements)

    def test_candidate_rows_tolerate_missing_sector_context_table(self) -> None:
        cursor = FakeCursor()
        cursor._one = {"table_ref": None}

        rows = sql.fetch_candidate_rows(
            cursor,
            source_schema="trading_data",
            source_table="model_03_target_state_vector_data_acquisition",
            sector_context_schema="trading_model",
            sector_context_table="model_02_sector_context",
            source_start="2016-01-01",
            source_end="2016-02-01",
            target_context_mapping_path=None,
        )

        statements = "\n".join(statement for statement, _ in cursor.calls)
        self.assertEqual(rows, [])
        self.assertIn('COALESCE(NULL::text, NULL::text)', statements)
        self.assertNotIn('FROM "trading_model"."model_02_sector_context" AS l2', statements)

    def test_candidate_rows_use_accepted_target_context_mapping(self) -> None:
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
            cursor._one = {"table_ref": "trading_data.model_02_sector_context_data_acquisition"}

            sql.fetch_candidate_rows(
                cursor,
                source_schema="trading_data",
                source_table="model_03_target_state_vector_data_acquisition",
                sector_context_schema="trading_model",
                sector_context_table="m02_sector_context_model_generation",
                target_context_mapping_path=mapping_path,
            )

        statements = "\n".join(statement for statement, _ in cursor.calls)
        params = [param for _, call_params in cursor.calls for param in call_params]
        self.assertIn("WITH target_context_mapping", statements)
        self.assertIn("mapping_l2.layer2_context_symbol", statements)
        self.assertIn("mapping_l2.target_asset_class", statements)
        self.assertIn("mapping_l2.optionable_proxy_status", statements)
        self.assertIn('AS "target_asset_class"', statements)
        self.assertIn('AS "optionable_underlying_status"', statements)
        self.assertIn('COALESCE(direct_l2."sector_or_industry_symbol", mapping_l2.layer2_context_symbol)', statements)
        self.assertIn("AAPL", params)
        self.assertIn("XLK", params)
        self.assertIn("equity_common", params)
        self.assertNotIn("MSFT", params)

    def test_context_rows_keep_prior_point_in_time_context_before_source_start(self) -> None:
        cursor = FakeCursor()
        cursor._one = {"table_ref": "trading_model.model_01_market_regime_model_generation"}

        sql.fetch_context_rows(
            cursor,
            schema="trading_model",
            table="m01_market_regime_model_generation",
            ref_column="market_context_state_ref",
            source_start="2016-01-04T09:30:00-05:00",
            source_end="2016-01-04T16:00:00-05:00",
        )

        statement, params = cursor.calls[-1]
        self.assertNotIn("available_time >= %s", statement)
        self.assertIn("available_time < %s", statement)
        self.assertEqual(params, ["2016-01-04T16:00:00-05:00"])

    def test_context_rows_can_filter_to_required_context_symbols(self) -> None:
        cursor = FakeCursor()
        cursor._one = {"table_ref": "trading_model.model_02_sector_context_model_generation"}

        sql.fetch_context_rows(
            cursor,
            schema="trading_model",
            table="m02_sector_context_model_generation",
            ref_column="sector_context_state_ref",
            source_end="2016-02-01T00:00:00-05:00",
            filter_column="sector_or_industry_symbol",
            filter_values=["xlk", "XLK", ""],
        )

        statement, params = cursor.calls[-1]
        self.assertIn('UPPER("sector_or_industry_symbol"::text) = ANY(%s)', statement)
        self.assertEqual(params, ["2016-02-01T00:00:00-05:00", ["XLK"]])

    def test_context_rows_tolerate_missing_context_table(self) -> None:
        cursor = FakeCursor()
        cursor._one = {"table_ref": None}

        rows = sql.fetch_context_rows(
            cursor,
            schema="trading_model",
            table="model_02_sector_context",
            ref_column="sector_context_state_ref",
            source_end="2016-01-04T16:00:00-05:00",
        )

        self.assertEqual(rows, [])
        self.assertEqual(len(cursor.calls), 1)
        self.assertIn("SELECT to_regclass", cursor.calls[0][0])

    def test_option_chain_rows_are_optional_and_half_open(self) -> None:
        cursor = FakeCursor()
        cursor._one = {"table_ref": "trading_data.option_chain_state_source"}

        sql.fetch_option_chain_rows(
            cursor,
            source_schema="trading_data",
            source_table="option_chain_state_source",
            source_start="2026-01-01T00:00:00-05:00",
            source_end="2026-02-01T00:00:00-05:00",
            underlyings=["aapl", "AAPL", ""],
        )

        statements = "\n".join(statement for statement, _ in cursor.calls)
        params = [param for _, call_params in cursor.calls for param in call_params]
        self.assertIn("SELECT to_regclass", cursor.calls[0][0])
        self.assertIn('FROM "trading_data"."option_chain_state_source"', statements)
        self.assertIn("snapshot_time >= %s", statements)
        self.assertIn("snapshot_time < %s", statements)
        self.assertIn('UPPER("underlying"::text) = ANY(%s)', statements)
        self.assertNotIn("snapshot_time <= %s", statements)
        self.assertEqual(params, ["trading_data.option_chain_state_source", "2026-01-01T00:00:00-05:00", "2026-02-01T00:00:00-05:00", ["AAPL"]])

    def test_missing_option_chain_table_returns_empty_rows(self) -> None:
        cursor = FakeCursor()
        cursor._one = {"table_ref": None}

        rows = sql.fetch_option_chain_rows(cursor, source_schema="trading_data", source_table="option_chain_state_source")

        self.assertEqual(rows, [])
        self.assertEqual(len(cursor.calls), 1)

    def test_bounded_generation_uses_windowed_source_fetch_and_reports_progress(self) -> None:
        cursor = FakeCursor()
        progress_calls: list[dict[str, object]] = []

        def fail_full_fetch(*args, **kwargs):
            raise AssertionError("bounded generation must not fetch the full source window before slicing")

        with (
            patch.object(sql, "_load_psycopg", return_value=(FakePsycopg(cursor), object())),
            patch.object(sql, "_load_generator", return_value=FakeGenerator()),
            patch.object(sql, "fetch_candidate_rows", return_value=[{"symbol": "AAPL", "sector_context_symbol": "XLK"}]),
            patch.object(sql, "fetch_context_rows", return_value=[]),
            patch.object(sql, "fetch_source_rows", side_effect=fail_full_fetch),
            patch.object(sql, "fetch_source_rows_with_lookback", return_value=[]),
            patch.object(sql, "fetch_option_chain_rows", return_value=[]),
            patch.object(sql, "_write_task_progress", side_effect=lambda **kwargs: progress_calls.append(kwargs)),
        ):
            row_count = sql.generate_sql(
                database_url="postgresql://example.invalid/db",
                source_schema="trading_data",
                source_table="model_03_target_state_vector_data_acquisition",
                target_schema="trading_data",
                target_table="model_03_target_state_vector_feature_generation",
                source_start="2016-01-01T00:00:00-05:00",
                source_end="2016-01-15T00:00:00-05:00",
                market_context_schema="trading_model",
                market_context_table="m01_market_regime_model_generation",
                sector_context_schema="trading_model",
                sector_context_table="m02_sector_context_model_generation",
                target_context_mapping_path=None,
                option_chain_source_schema="trading_data",
                option_chain_source_table="option_chain_state_source",
                run_id="test_run",
                target_context_state_version="target_context_state",
            )

        self.assertEqual(row_count, 2)
        self.assertIn("feature_generation_prepare", [call["node_id"] for call in progress_calls])
        self.assertEqual(progress_calls[0]["expected_count"], 2)
        completed = [call for call in progress_calls if call["node_id"] == "feature_generation_window_completed"]
        self.assertEqual([call["processed_count"] for call in completed], [1, 2])


if __name__ == "__main__":
    unittest.main()
