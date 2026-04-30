from __future__ import annotations

import importlib
import importlib.util
import math
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
generator = importlib.import_module("data_feature.feature_01_market_regime.generator")
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_feature_01_market_regime.py"
SCRIPT_SPEC = importlib.util.spec_from_file_location("generate_feature_01_market_regime", SCRIPT_PATH)
sql_runner = importlib.util.module_from_spec(SCRIPT_SPEC)
assert SCRIPT_SPEC and SCRIPT_SPEC.loader
SCRIPT_SPEC.loader.exec_module(sql_runner)


def _bar(symbol: str, day: date, close: float, *, timeframe: str = "1Day", open_: float | None = None, high: float | None = None, low: float | None = None) -> dict[str, str]:
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "timestamp": datetime.combine(day, datetime.min.time(), tzinfo=ET).isoformat(),
        "bar_open": str(open_ if open_ is not None else close * 0.99),
        "bar_high": str(high if high is not None else close * 1.02),
        "bar_low": str(low if low is not None else close * 0.98),
        "bar_close": str(close),
        "bar_volume": "1000",
    }


def _intraday_bar(symbol: str, timestamp: datetime, close: float) -> dict[str, str]:
    return {
        "symbol": symbol,
        "timeframe": "30Min",
        "timestamp": timestamp.isoformat(),
        "bar_open": str(close * 0.999),
        "bar_high": str(close * 1.001),
        "bar_low": str(close * 0.998),
        "bar_close": str(close),
        "bar_volume": "1000",
    }


class MarketRegimeGeneratorTests(unittest.TestCase):
    def _inputs(self):
        universe = [
            {"symbol": "SPY", "universe_type": "market_state_etf"},
            {"symbol": "QQQ", "universe_type": "market_state_etf"},
            {"symbol": "XLK", "universe_type": "sector_observation_etf"},
            {"symbol": "XLP", "universe_type": "sector_observation_etf"},
        ]
        combinations = [
            {
                "combination_id": "qqq_spy",
                "combination_type": "primary",
                "numerator_symbol": "QQQ",
                "denominator_symbol": "SPY",
                "feature_bar_grain": "30m",
            },
            {
                "combination_id": "xlk_spy",
                "combination_type": "sector_rotation",
                "numerator_symbol": "XLK",
                "denominator_symbol": "SPY",
                "feature_bar_grain": "30m",
            },
        ]
        start = date(2025, 1, 1)
        bars: list[dict[str, str]] = []
        for index in range(270):
            day = start + timedelta(days=index)
            spy_close = 100 + index + math.sin(index / 4)
            qqq_close = 200 + index * 1.2 + math.sin(index / 3)
            xlk_close = 90 + index * 0.8 + math.sin(index / 5)
            xlp_close = 80 + index * 0.3 + math.cos(index / 7)
            for symbol, close in {"SPY": spy_close, "QQQ": qqq_close, "XLK": xlk_close, "XLP": xlp_close}.items():
                bars.append(_bar(symbol, day, close))
        snapshot = datetime.combine(start + timedelta(days=269), datetime.min.time(), tzinfo=ET).replace(hour=16)
        bars.extend(
            [
                _intraday_bar("SPY", snapshot - timedelta(minutes=30), 369.0),
                _intraday_bar("SPY", snapshot, 370.0),
                _intraday_bar("QQQ", snapshot - timedelta(minutes=30), 520.0),
                _intraday_bar("QQQ", snapshot, 525.0),
            ]
        )
        return generator.build_inputs(bar_rows=bars, universe_rows=universe, combination_rows=combinations), snapshot

    def test_generates_wide_market_regime_features(self) -> None:
        inputs, snapshot = self._inputs()

        row = generator.generate_row(inputs, snapshot)

        self.assertEqual(row["snapshot_time"], snapshot.isoformat())
        self.assertAlmostEqual(row["spy_return_30m"], math.log(370.0 / 369.0))
        self.assertAlmostEqual(row["qqq_spy_30m"], math.log((525.0 / 370.0) / (520.0 / 369.0)))
        self.assertIn("spy_realized_vol_20d", row)
        self.assertIn("qqq_spy_realized_vol_20d_ratio", row)
        self.assertIn("qqq_spy_ma20", row)
        self.assertIn("qqq_spy_distance_to_ma20", row)
        self.assertIn("qqq_spy_return_corr_20d", row)
        self.assertFalse(any(key.startswith("xlk_spy") for key in row))
        self.assertIn("market_state_avg_return_corr_20d", row)
        self.assertIn("sector_observation_positive_return_1d_pct", row)
        self.assertFalse(any(key.startswith("rs_") for key in row))

    def test_daily_bars_are_not_available_before_regular_close(self) -> None:
        inputs, snapshot = self._inputs()
        before_close = snapshot.replace(hour=15, minute=59)
        row_before_close = generator.generate_row(inputs, before_close)
        row_at_close = generator.generate_row(inputs, snapshot)

        self.assertNotEqual(row_before_close["spy_return_1d"], row_at_close["spy_return_1d"])

    def test_sql_writer_stores_generated_features_in_jsonb_payload(self) -> None:
        class FakeCursor:
            def __init__(self) -> None:
                self.calls: list[tuple[str, list[object] | None]] = []

            def execute(self, sql: str, params: list[object] | None = None) -> None:
                self.calls.append((sql, params))

        cursor = FakeCursor()
        rows = [
            {
                "snapshot_time": "2026-01-02T16:00:00-05:00",
                "spy_return_30m": 0.01,
                "qqq_spy_return_corr_20d": None,
            }
        ]

        sql_runner.write_feature_rows_sql(
            cursor,
            rows,
            target_schema="trading_data",
            target_table="feature_01_market_regime",
        )

        joined_sql = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn('CREATE TABLE IF NOT EXISTS "trading_data"."feature_01_market_regime"', joined_sql)
        self.assertIn('"feature_payload_json" JSONB NOT NULL DEFAULT', joined_sql)
        self.assertNotIn('ADD COLUMN IF NOT EXISTS "spy_return_30m" DOUBLE PRECISION', joined_sql)
        self.assertIn('ON CONFLICT ("snapshot_time") DO UPDATE SET', joined_sql)
        insert_params = cursor.calls[-1][1]
        self.assertIsNotNone(insert_params)
        self.assertEqual(insert_params[0], "2026-01-02T16:00:00-05:00")
        self.assertIn('"spy_return_30m": 0.01', insert_params[1])

    def test_inferred_snapshots_use_30_minute_decision_surface(self) -> None:
        inputs, snapshot = self._inputs()
        inferred = generator.infer_snapshot_times(inputs)

        self.assertIn(snapshot, inferred)
        self.assertIn(snapshot - timedelta(minutes=30), inferred)
        self.assertNotIn(snapshot.replace(hour=9, minute=30), inferred)

    @unittest.skipUnless(
        Path("/root/projects/trading-storage/main/shared/market_regime_etf_universe.csv").exists()
        and Path("/root/projects/trading-storage/main/shared/market_regime_relative_strength_combinations.csv").exists(),
        "shared market-regime CSVs are unavailable",
    )
    def test_current_shared_contract_generates_expected_width(self) -> None:
        inputs = generator.build_inputs(
            bar_rows=[],
            universe_rows=generator.read_csv_rows("/root/projects/trading-storage/main/shared/market_regime_etf_universe.csv"),
            combination_rows=generator.read_csv_rows("/root/projects/trading-storage/main/shared/market_regime_relative_strength_combinations.csv"),
        )

        row = generator.generate_row(inputs, datetime(2026, 1, 2, 16, 0, tzinfo=ET))

        self.assertEqual(len(row), 968)
        self.assertFalse(any(key.startswith("xlk_spy") for key in row))
        self.assertFalse(any(key.startswith("smh_xlk") for key in row))
        self.assertTrue(any(key.startswith("qqq_spy") for key in row))


if __name__ == "__main__":
    unittest.main()
