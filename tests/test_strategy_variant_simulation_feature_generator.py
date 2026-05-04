from __future__ import annotations

import importlib
import importlib.util
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
generator = importlib.import_module("data_feature.feature_03_strategy_variant_simulation.generator")
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_feature_03_strategy_variant_simulation.py"
SCRIPT_SPEC = importlib.util.spec_from_file_location("generate_feature_03_strategy_variant_simulation", SCRIPT_PATH)
sql_runner = importlib.util.module_from_spec(SCRIPT_SPEC)
assert SCRIPT_SPEC and SCRIPT_SPEC.loader
SCRIPT_SPEC.loader.exec_module(sql_runner)


def _bar(symbol: str, timestamp: datetime, close: float) -> dict[str, str]:
    return {
        "symbol": symbol,
        "timestamp": timestamp.isoformat(),
        "bar_open": str(close),
        "bar_high": str(close + 0.1),
        "bar_low": str(close - 0.1),
        "bar_close": str(close),
        "bar_volume": "1000",
    }


def _variant(**overrides: object) -> dict[str, object]:
    params: dict[str, object] = {
        "ma_window_profile": "micro_3_10",
        "price_field": "bar_close",
        "ma_type": "sma",
        "crossover_confirmation_bars": 1,
        "cooldown_bars": 0,
        "min_slope": 0,
    }
    params.update(dict(overrides.pop("params", {}) or {}))
    row: dict[str, object] = {
        "strategy_family": "moving_average_crossover",
        "strategy_variant": "ma_cross__micro_3_10__close__sma",
        "variant_spec_ref": "family_01@fixture",
        "params": params,
    }
    row.update(overrides)
    return row


class StrategyVariantSimulationFeatureTests(unittest.TestCase):
    def test_generates_point_in_time_variant_path_for_anonymous_candidate(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        closes = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 12, 14, 16]
        inputs = generator.build_inputs(
            bar_rows=[_bar("AAPL", start + timedelta(minutes=index), close) for index, close in enumerate(closes)],
            candidate_rows=[{"target_candidate_id": "tc_001", "symbol": "AAPL"}],
            variant_rows=[_variant()],
        )

        rows = generator.generate_rows(inputs, run_id="sim_001")

        self.assertEqual(len(rows), len(closes))
        self.assertEqual({row["target_candidate_id"] for row in rows}, {"tc_001"})
        self.assertEqual({row["3_strategy_family"] for row in rows}, {"moving_average_crossover"})
        self.assertNotIn("symbol", rows[0])

        first_long = next(row for row in rows if row["signal_state"] == "long")
        self.assertEqual(first_long["available_time"], (start + timedelta(minutes=10)).isoformat())
        self.assertEqual(first_long["exposure_before_bar"], 0)
        self.assertEqual(first_long["exposure"], 1)
        self.assertEqual(first_long["entry_state"], "enter_long")

        next_row = rows[11]
        self.assertEqual(next_row["exposure_before_bar"], 1)
        self.assertAlmostEqual(next_row["variant_return"], 14 / 12 - 1)

    def test_rejects_unsupported_family_before_silent_simulation(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        with self.assertRaisesRegex(generator.StrategyVariantSimulationError, "unsupported"):
            generator.build_inputs(
                bar_rows=[_bar("AAPL", start, 10)],
                candidate_rows=[{"target_candidate_id": "tc_001", "symbol": "AAPL"}],
                variant_rows=[{"strategy_family": "unknown", "strategy_variant": "x", "params": {"ma_window_profile": "micro_3_10"}}],
            )

    def test_sql_writer_persists_feature_payload_json(self) -> None:
        class FakeCursor:
            def __init__(self) -> None:
                self.calls: list[tuple[str, list[object] | None]] = []

            def execute(self, sql: str, params: list[object] | None = None) -> None:
                self.calls.append((sql, params))

        cursor = FakeCursor()
        rows = [
            {
                "run_id": "sim_001",
                "available_time": "2026-01-02T09:40:00-05:00",
                "target_candidate_id": "tc_001",
                "3_strategy_family": "moving_average_crossover",
                "3_strategy_variant": "ma_cross__micro_3_10__close__sma",
                "variant_spec_ref": "family_01@fixture",
                "signal_state": "long",
                "exposure": 1,
                "exposure_before_bar": 0,
                "variant_return": 0.0,
            }
        ]

        sql_runner.write_feature_rows_sql(cursor, rows, target_schema="trading_data", target_table="feature_03_strategy_variant_simulation")

        joined_sql = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn('CREATE TABLE IF NOT EXISTS "trading_data"."feature_03_strategy_variant_simulation"', joined_sql)
        self.assertIn('PRIMARY KEY ("run_id", "available_time", "target_candidate_id", "3_strategy_family", "3_strategy_variant")', joined_sql)
        self.assertIn('ON CONFLICT ("run_id", "available_time", "target_candidate_id", "3_strategy_family", "3_strategy_variant") DO UPDATE SET', joined_sql)
        insert_params = cursor.calls[-1][1]
        self.assertIsNotNone(insert_params)
        self.assertEqual(insert_params[:8], ["sim_001", "2026-01-02T09:40:00-05:00", "tc_001", "moving_average_crossover", "ma_cross__micro_3_10__close__sma", "family_01@fixture", "long", 1])
        payload = json.loads(insert_params[8])  # type: ignore[index]
        self.assertEqual(payload["exposure_before_bar"], 0)
        self.assertEqual(payload["variant_return"], 0.0)


if __name__ == "__main__":
    unittest.main()
