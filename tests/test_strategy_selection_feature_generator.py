from __future__ import annotations

import importlib
import importlib.util
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
generator = importlib.import_module("data_feature.feature_03_strategy_selection.generator")
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_feature_03_strategy_selection.py"
SCRIPT_SPEC = importlib.util.spec_from_file_location("generate_feature_03_strategy_selection", SCRIPT_PATH)
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


class StrategySelectionFeatureTests(unittest.TestCase):
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

    def test_accepts_model_shaped_variant_configs_for_all_active_families(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        closes = [100 + (index * 0.2) + (3 if index > 45 else 0) for index in range(90)]
        bar_rows = []
        for index, close in enumerate(closes):
            row = _bar("AAPL", start + timedelta(minutes=index), close)
            row["bar_volume"] = str(1000 + index * 10)
            row["spread_bps"] = "4"
            row["bar_vwap"] = str(close - 0.2)
            bar_rows.append(row)
        variants = [
            ("moving_average_crossover", {"ma_window_profile": "micro_3_10", "price_field": "bar_close", "ma_type": "sma", "crossover_confirmation_bars": 1, "cooldown_bars": 1, "min_slope": 0}),
            ("donchian_channel_breakout", {"channel_window_profile": "micro_10_5_atr10", "confirmation_bars": 1, "breakout_buffer_atr": 0, "min_atr_pct": 0.004, "cooldown_bars": 1}),
            ("macd_trend", {"macd_profile": "micro_3_10_3", "histogram_threshold": "0", "zero_line_filter": False, "slope_confirmation_bars": 1, "exit_on_signal_cross": True, "cooldown_bars": 1}),
            ("bollinger_band_reversion", {"band_window_profile": "micro_10", "band_stddev": 1.5, "entry_band": "outer_touch", "exit_band": "midline", "trend_filter_enabled": False, "max_hold_minutes": 30}),
            ("rsi_reversion", {"rsi_period_profile": "micro_5", "threshold_pair": (30, 70), "exit_midline": "50_cross", "divergence_required": False, "multi_duration_confirm": False, "cooldown_bars": 1}),
            ("bias_reversion", {"ma_window_profile": "micro_10", "ma_type": "sma", "deviation_measure": "pct_from_ma", "entry_deviation_threshold": 1.5, "exit_deviation_threshold": 0.5, "trend_filter_enabled": False}),
            ("vwap_reversion", {"deviation_bps": 30, "entry_zscore": 1.0, "exit_zscore": 0.5, "maximum_spread_bps": 5}),
            ("range_breakout", {"range_window_profile": "micro_10", "range_width_max_atr": 3.0, "breakout_buffer_atr": 0, "volume_confirmation_ratio": 1.0, "retest_rule": "none", "cooldown_bars": 1}),
            ("opening_range_breakout", {"opening_range_minutes": 5, "breakout_buffer_bps": 5, "volume_confirmation_ratio": 1.0}),
            ("volatility_breakout", {"volatility_profile": "micro_atr10_x1.25", "direction_filter": "none", "confirmation_bars": 1, "stop_atr_multiple": 1.5, "cooldown_bars": 1}),
        ]
        variant_rows = [
            {
                "3_strategy_family": family,
                "3_strategy_variant": f"{family}.fixture",
                "strategy_spec_hash": f"hash_{family}",
                "fixed_parameters": {"signal_bar_interval": "1Min"},
                "variable_parameters": params,
            }
            for family, params in variants
        ]

        inputs = generator.build_inputs(
            bar_rows=bar_rows,
            candidate_rows=[{"target_candidate_id": "tc_001", "symbol": "AAPL"}],
            variant_rows=variant_rows,
        )
        rows = generator.generate_rows(inputs, run_id="all_family_smoke")

        self.assertEqual({row["3_strategy_family"] for row in rows}, {family for family, _params in variants})
        self.assertEqual(len(rows), len(closes) * len(variants))
        self.assertFalse(any("symbol" in row for row in rows))

    def test_donchian_requires_close_break_confirmation_and_atr_gate(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        closes = [100] * 10 + [101, 102, 103]
        bar_rows = [_bar("AAPL", start + timedelta(minutes=index), close) for index, close in enumerate(closes)]
        confirmed_variant = {
            "strategy_family": "donchian_channel_breakout",
            "strategy_variant": "donchian.confirmed.fixture",
            "variant_spec_ref": "family_02@fixture",
            "params": {
                "channel_window_profile": "micro_10_5_atr10",
                "confirmation_bars": 2,
                "breakout_buffer_atr": 0,
                "min_atr_pct": 0,
                "cooldown_bars": 0,
            },
        }
        gated_variant = {
            **confirmed_variant,
            "strategy_variant": "donchian.gated.fixture",
            "params": {**confirmed_variant["params"], "confirmation_bars": 1, "min_atr_pct": 0.10},
        }
        inputs = generator.build_inputs(
            bar_rows=bar_rows,
            candidate_rows=[{"target_candidate_id": "tc_001", "symbol": "AAPL"}],
            variant_rows=[confirmed_variant, gated_variant],
        )

        rows = generator.generate_rows(inputs, run_id="donchian_contract")
        confirmed_rows = [row for row in rows if row["3_strategy_variant"] == "donchian.confirmed.fixture"]
        gated_rows = [row for row in rows if row["3_strategy_variant"] == "donchian.gated.fixture"]

        first_long = next(row for row in confirmed_rows if row["signal_state"] == "long")
        self.assertEqual(first_long["available_time"], (start + timedelta(minutes=11)).isoformat())
        self.assertEqual(first_long["signal_reason"], "donchian_upper_break")
        self.assertTrue(all(row["signal_state"] != "long" for row in gated_rows))
        self.assertIn("min_atr_pct_gate", {row["signal_reason"] for row in gated_rows})

    def test_rejects_unsupported_family_before_silent_simulation(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        with self.assertRaisesRegex(generator.StrategySelectionError, "unsupported"):
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

        sql_runner.write_feature_rows_sql(cursor, rows, target_schema="trading_data", target_table="feature_03_strategy_selection")

        joined_sql = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn('CREATE TABLE IF NOT EXISTS "trading_data"."feature_03_strategy_selection"', joined_sql)
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
