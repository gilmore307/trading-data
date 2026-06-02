from __future__ import annotations

import importlib
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
generator = importlib.import_module("data_feature.m03_target_state_vector_feature_generation.generator")


def _assert_nested_close(test_case: unittest.TestCase, left, right) -> None:
    if isinstance(left, dict) and isinstance(right, dict):
        test_case.assertEqual(set(left), set(right))
        for key in left:
            _assert_nested_close(test_case, left[key], right[key])
    elif isinstance(left, float) or isinstance(right, float):
        test_case.assertAlmostEqual(left, right, places=12)
    else:
        test_case.assertEqual(left, right)


def _bar(symbol: str, timestamp: datetime, close: float, *, volume: int = 1000) -> dict[str, str]:
    return {
        "symbol": symbol,
        "timestamp": timestamp.isoformat(),
        "bar_open": str(close - 0.05),
        "bar_high": str(close + 0.25),
        "bar_low": str(close - 0.25),
        "bar_close": str(close),
        "bar_volume": str(volume),
        "bar_vwap": str(close - 0.1),
        "dollar_volume": str(close * volume),
        "spread_bps": "4",
    }


class TargetStateVectorFeatureTests(unittest.TestCase):
    def test_generates_four_block_state_vector_without_symbol_leakage(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        bar_rows = [_bar("AAPL", start + timedelta(minutes=index), 100 + index, volume=1000 + index) for index in range(70)]
        inputs = generator.build_inputs(
            bar_rows=bar_rows,
            candidate_rows=[{"target_candidate_id": "tc_001", "symbol": "AAPL"}],
            market_context_rows=[
                {
                    "available_time": (start + timedelta(minutes=10)).isoformat(),
                    "market_context_state_ref": "mkt_001",
                    "market_regime_state": "risk_on",
                    "market_return_1h": 0.03,
                    "market_volatility_1h": 0.01,
                }
            ],
            sector_context_rows=[
                {
                    "available_time": (start + timedelta(minutes=10)).isoformat(),
                    "sector_context_state_ref": "sec_001",
                    "sector_context_state": "leadership_stable",
                    "sector_return_1h": 0.06,
                    "sector_volatility_1h": 0.015,
                }
            ],
        )

        rows = generator.generate_rows(inputs, run_id="state")

        self.assertEqual(len(rows), 70)
        self.assertEqual({row["target_candidate_id"] for row in rows}, {"tc_001"})
        self.assertFalse(any("symbol" in row for row in rows))
        row = rows[65]
        self.assertEqual(row["run_id"], "state")
        self.assertEqual(row["market_context_state_ref"], "mkt_001")
        self.assertEqual(row["sector_context_state_ref"], "sec_001")
        expected_windows = ["10min", "1h", "1D", "1W"]
        for block in ("market_state_features", "sector_state_features", "target_state_features", "cross_state_features"):
            self.assertIn(block, row)
            self.assertIsInstance(row[block], dict)
            self.assertEqual(row[block]["state_observation_windows"], expected_windows)
            self.assertEqual(
                row[block]["state_window_sync_policy"],
                "market_sector_target_blocks_must_share_identical_observation_windows",
            )

        target_state = row["target_state_features"]
        self.assertEqual(set(target_state["multi_frame_state"]), set(expected_windows))
        self.assertAlmostEqual(target_state["multi_frame_state"]["10min"]["return"], 165 / 155 - 1)
        self.assertIn("path_stability", target_state["multi_frame_state"]["10min"])
        self.assertAlmostEqual(target_state["target_direction_return_shape"]["return_10min"], 165 / 155 - 1)
        self.assertIn("target_liquidity_tradability_state", target_state)
        self.assertIn("target_trend_age_state", target_state)
        self.assertIn("target_exhaustion_decay_state", target_state)
        self.assertIn("target_peer_rank_state", target_state)
        self.assertEqual(target_state["target_liquidity_tradability_state"]["spread_bps"], 4.0)
        self.assertEqual(target_state["target_session_position_state"]["minutes_since_open"], 65)
        self.assertEqual(target_state["target_session_position_state"]["session_phase"], "midday")
        self.assertGreater(target_state["target_vwap_location_state"]["vwap_distance_pct"], 0)

        cross_state = row["cross_state_features"]
        self.assertEqual(set(cross_state["multi_frame_state"]), set(expected_windows))
        self.assertAlmostEqual(cross_state["multi_frame_state"]["1h"]["target_vs_market_residual_direction"], (165 / 105 - 1) - 0.03)
        self.assertAlmostEqual(cross_state["target_vs_market_residual_direction"], (165 / 105 - 1) - 0.03)
        self.assertAlmostEqual(cross_state["target_vs_sector_residual_direction"], (165 / 105 - 1) - 0.06)
        self.assertEqual(cross_state["sector_confirmation_state"], "sector_confirmed")
        self.assertIn("beta_adjustment_policy", cross_state)

    def test_uses_sparse_state_windows_without_variant_fields(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        inputs = generator.build_inputs(
            bar_rows=[_bar("MSFT", start + timedelta(minutes=index), 50 + index) for index in range(70)],
            candidate_rows=[{"target_candidate_id": "tc_002", "symbol": "MSFT"}],
        )

        rows = generator.generate_rows(inputs)
        target_state = rows[-1]["target_state_features"]

        self.assertEqual(set(target_state["target_direction_return_shape"]), {"return_10min", "return_1h", "return_1D", "return_1W"})
        self.assertNotIn("3_strategy_family", rows[-1])
        self.assertNotIn("3_strategy_variant", rows[-1])
        self.assertNotIn("strategy_variant", repr(rows[-1]))

    def test_rejects_unmapped_bars_instead_of_emitting_identity_features(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        with self.assertRaisesRegex(generator.TargetStateVectorError, "candidate-mapped bar"):
            generator.build_inputs(
                bar_rows=[_bar("AAPL", start, 100)],
                candidate_rows=[{"target_candidate_id": "tc_001", "symbol": "MSFT"}],
            )

    def test_sector_context_rows_are_filtered_by_candidate_sector_symbol(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        inputs = generator.build_inputs(
            bar_rows=[_bar("AAPL", start + timedelta(minutes=index), 100 + index) for index in range(12)],
            candidate_rows=[{"target_candidate_id": "tc_001", "symbol": "AAPL", "sector_context_symbol": "XLK"}],
            sector_context_rows=[
                {
                    "available_time": start.isoformat(),
                    "sector_or_industry_symbol": "XLE",
                    "sector_context_state_ref": "sec_energy",
                    "sector_return_1h": -0.04,
                },
                {
                    "available_time": start.isoformat(),
                    "sector_or_industry_symbol": "XLK",
                    "sector_context_state_ref": "sec_tech",
                    "sector_return_1h": 0.05,
                },
            ],
        )

        rows = generator.generate_rows(inputs)

        self.assertEqual(rows[-1]["sector_context_state_ref"], "sec_tech")
        self.assertNotEqual(rows[-1]["sector_context_state_ref"], "sec_energy")

    def test_context_lookup_uses_latest_prior_context_when_rows_are_unsorted(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        inputs = generator.build_inputs(
            bar_rows=[_bar("AAPL", start + timedelta(minutes=index), 100 + index) for index in range(12)],
            candidate_rows=[{"target_candidate_id": "tc_001", "symbol": "AAPL"}],
            market_context_rows=[
                {"available_time": (start + timedelta(minutes=10)).isoformat(), "market_context_state_ref": "mkt_late"},
                {"available_time": (start + timedelta(minutes=5)).isoformat(), "market_context_state_ref": "mkt_early"},
            ],
        )

        rows = generator.generate_rows(inputs)

        self.assertIsNone(rows[4]["market_context_state_ref"])
        self.assertEqual(rows[5]["market_context_state_ref"], "mkt_early")
        self.assertEqual(rows[-1]["market_context_state_ref"], "mkt_late")

    def test_rolling_feature_cache_matches_window_fallbacks(self) -> None:
        closes = [100.0 + ((index % 17) - 8) * 0.13 + index * 0.02 for index in range(150)]
        highs = [value + 0.35 for value in closes]
        lows = [value - 0.31 for value in closes]
        volumes = [1000.0 + (index % 11) * 17 for index in range(150)]
        vwaps = [value - 0.04 for value in closes]
        spreads = [4.0 for _ in closes]
        dollar_volumes = [close * volume for close, volume in zip(closes, volumes)]
        cache = generator._TargetRollingFeatures(closes, highs, lows, volumes, vwaps, dollar_volumes)

        for index in (12, 65, 120, 149):
            cached = generator._target_state_features(
                index,
                closes,
                highs,
                lows,
                volumes,
                vwaps,
                spreads,
                dollar_volumes,
                feature_cache=cache,
            )
            fallback = generator._target_state_features(index, closes, highs, lows, volumes, vwaps, spreads, dollar_volumes)
            self.assertEqual(cached["target_price_state"], fallback["target_price_state"])
            self.assertEqual(cached["target_session_position_state"], fallback["target_session_position_state"])
            for block in (
                "target_direction_return_shape",
                "target_trend_quality_state",
                "target_trend_age_state",
                "target_exhaustion_decay_state",
                "target_volatility_range_state",
                "target_volume_activity_state",
            ):
                _assert_nested_close(self, cached[block], fallback[block])


if __name__ == "__main__":
    unittest.main()
