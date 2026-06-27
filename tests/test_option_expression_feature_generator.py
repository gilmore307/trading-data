from __future__ import annotations

import unittest

from data_feature.m05_option_expression_feature_generation.generator import generate_rows


class OptionExpressionFeatureGeneratorTests(unittest.TestCase):
    def test_generates_option_candidate_feature_payload(self) -> None:
        rows = generate_rows(
            [
                {
                    "underlying": "AAPL",
                    "snapshot_time": "2026-05-08T14:30:00Z",
                    "snapshot_type": "entry",
                    "option_symbol": "AAPL260515C00270000",
                    "expiration": "2026-05-15",
                    "option_right_type": "call",
                    "strike": 270,
                    "bid": 1.0,
                    "ask": 1.2,
                    "bid_size": 20,
                    "ask_size": 10,
                    "implied_vol": 0.35,
                    "delta": 0.42,
                    "theta": -0.03,
                    "vega": 0.12,
                    "rho": 0.01,
                    "underlying_price": 260,
                    "days_to_expiration": 7,
                }
            ],
            run_id="unit_run",
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["run_id"], "unit_run")
        self.assertEqual(row["source_run_ref"], "option_chain_state_source")
        self.assertEqual(row["underlying"], "AAPL")
        payload = row["feature_payload_json"]
        self.assertAlmostEqual(payload["mid"], 1.1)
        self.assertAlmostEqual(payload["spread"], 0.2)
        self.assertAlmostEqual(payload["spread_pct_mid"], 0.2 / 1.1)
        self.assertAlmostEqual(payload["moneyness"], (260 / 270) - 1)
        self.assertAlmostEqual(payload["quote_size_balance"], (20 - 10) / (20 + 10))
        self.assertTrue(row["feature_quality_diagnostics"]["has_required_fields"])

    def test_skips_rows_without_snapshot_identity(self) -> None:
        rows = generate_rows([
            {"underlying": "AAPL", "snapshot_time": "2026-05-08T14:30:00Z"},
            {"snapshot_type": "entry", "option_symbol": "AAPL260515C00270000"},
        ])
        self.assertEqual(rows, [])

    def test_zero_underlying_price_has_null_moneyness(self) -> None:
        rows = generate_rows(
            [
                {
                    "underlying": "AAOI",
                    "snapshot_time": "2022-09-14T16:00:00Z",
                    "snapshot_type": "source_cache",
                    "option_symbol": "AAOI220916P00005000",
                    "expiration": "2022-09-16",
                    "option_right_type": "put",
                    "strike": 5,
                    "underlying_price": 0,
                }
            ],
            run_id="unit_run",
        )

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["feature_payload_json"]["moneyness"])


if __name__ == "__main__":
    unittest.main()
