from __future__ import annotations

import importlib
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
generator = importlib.import_module("data_feature.feature_03_target_state_vector.generator")


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
        bar_rows = [_bar("AAPL", start + timedelta(minutes=index), 100 + index, volume=1000 + index) for index in range(20)]
        inputs = generator.build_inputs(
            bar_rows=bar_rows,
            candidate_rows=[{"target_candidate_id": "tc_001", "symbol": "AAPL"}],
            market_context_rows=[
                {
                    "available_time": (start + timedelta(minutes=10)).isoformat(),
                    "market_context_state_ref": "mkt_001",
                    "market_regime_state": "risk_on",
                    "market_return_15min": 0.03,
                    "market_volatility_15min": 0.01,
                }
            ],
            sector_context_rows=[
                {
                    "available_time": (start + timedelta(minutes=10)).isoformat(),
                    "sector_context_state_ref": "sec_001",
                    "sector_context_state": "leadership_stable",
                    "sector_return_15min": 0.06,
                    "sector_volatility_15min": 0.015,
                }
            ],
        )

        rows = generator.generate_rows(inputs, run_id="state_v1")

        self.assertEqual(len(rows), 20)
        self.assertEqual({row["target_candidate_id"] for row in rows}, {"tc_001"})
        self.assertFalse(any("symbol" in row for row in rows))
        row = rows[15]
        self.assertEqual(row["run_id"], "state_v1")
        self.assertEqual(row["market_context_state_ref"], "mkt_001")
        self.assertEqual(row["sector_context_state_ref"], "sec_001")
        expected_windows = ["5min", "15min", "60min", "390min"]
        for block in ("market_state_features", "sector_state_features", "target_state_features", "cross_state_features"):
            self.assertIn(block, row)
            self.assertIsInstance(row[block], dict)
            self.assertEqual(row[block]["state_observation_windows"], expected_windows)
            self.assertEqual(
                row[block]["state_window_sync_policy"],
                "market_sector_target_blocks_must_share_identical_observation_windows",
            )

        target_state = row["target_state_features"]
        self.assertAlmostEqual(target_state["target_return_shape"]["return_15min"], 115 / 100 - 1)
        self.assertIn("target_liquidity_cost_state", target_state)
        self.assertEqual(target_state["target_liquidity_cost_state"]["spread_bps"], 4.0)
        self.assertGreater(target_state["target_vwap_location_state"]["vwap_distance_pct"], 0)

        cross_state = row["cross_state_features"]
        self.assertAlmostEqual(cross_state["target_vs_market_strength"], (115 / 100 - 1) - 0.03)
        self.assertAlmostEqual(cross_state["target_vs_sector_strength"], (115 / 100 - 1) - 0.06)
        self.assertEqual(cross_state["sector_confirmation_state"], "sector_confirmed")

    def test_uses_sparse_state_windows_without_variant_fields(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET)
        inputs = generator.build_inputs(
            bar_rows=[_bar("MSFT", start + timedelta(minutes=index), 50 + index) for index in range(70)],
            candidate_rows=[{"target_candidate_id": "tc_002", "symbol": "MSFT"}],
        )

        rows = generator.generate_rows(inputs)
        target_state = rows[-1]["target_state_features"]

        self.assertEqual(set(target_state["target_return_shape"]), {"return_5min", "return_15min", "return_60min", "return_390min"})
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


if __name__ == "__main__":
    unittest.main()
