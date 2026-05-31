from __future__ import annotations

import csv
import importlib
import json
import math
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
generator = importlib.import_module("data_feature.m01_market_regime_feature_generation.generator")
sql_runner = importlib.import_module("data_feature.m01_market_regime_feature_generation.sql")
from_feed_artifacts = importlib.import_module("data_feature.m01_market_regime_feature_generation.from_feed_artifacts")
runtime_config = importlib.import_module("data_runtime.config")


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
        "timeframe": "1Min",
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
            {"symbol": "SPY", "universe_type": "market_state_etf", "model_layer": "layer_01_market_regime"},
            {"symbol": "QQQ", "universe_type": "market_state_etf", "model_layer": "layer_01_market_regime"},
            {"symbol": "XLK", "universe_type": "sector_observation_etf", "model_layer": "layer_02_sector_context"},
            {"symbol": "XLP", "universe_type": "sector_observation_etf", "model_layer": "layer_02_sector_context"},
        ]
        combinations = [
            {
                "combination_id": "qqq_spy",
                "combination_type": "primary",
                "model_layer": "layer_01_market_regime",
                "numerator_symbol": "QQQ",
                "denominator_symbol": "SPY",
                "feature_bar_grain": "1m",
            },
            {
                "combination_id": "xlk_spy",
                "combination_type": "sector_rotation",
                "model_layer": "layer_02_sector_context",
                "numerator_symbol": "XLK",
                "denominator_symbol": "SPY",
                "feature_bar_grain": "1m",
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
                _intraday_bar("SPY", snapshot - timedelta(minutes=1), 369.0),
                _intraday_bar("SPY", snapshot, 370.0),
                _intraday_bar("QQQ", snapshot - timedelta(minutes=30), 520.0),
                _intraday_bar("QQQ", snapshot - timedelta(minutes=1), 520.0),
                _intraday_bar("QQQ", snapshot, 525.0),
            ]
        )
        return generator.build_inputs(bar_rows=bars, universe_rows=universe, combination_rows=combinations), snapshot

    def test_generates_wide_market_regime_features(self) -> None:
        inputs, snapshot = self._inputs()

        row = generator.generate_row(inputs, snapshot)

        self.assertEqual(row["snapshot_time"], snapshot.isoformat())
        self.assertEqual(row["input_frame"], "1h")
        self.assertEqual(row["prediction_horizon"], "1D")
        self.assertEqual(row["market_universe_ref"], "layer_01_02_market_context_etf_universe")
        self.assertAlmostEqual(row["spy_return_30m"], math.log(370.0 / 369.0))
        self.assertAlmostEqual(row["qqq_spy_1m"], math.log((525.0 / 370.0) / (520.0 / 369.0)))
        self.assertIn("spy_realized_vol_20d", row)
        self.assertIn("qqq_spy_realized_vol_20d_ratio", row)
        self.assertNotIn("qqq_spy_ma20", row)
        self.assertIn("qqq_spy_distance_to_ma20", row)
        self.assertIn("qqq_spy_return_corr_20d", row)
        self.assertFalse(any(key.startswith("xlk_spy") for key in row))
        self.assertIn("market_state_avg_return_corr_20d", row)
        self.assertFalse(any(key.startswith("sector_observation_") for key in row))
        self.assertFalse(any(key.startswith("rs_") for key in row))

    def test_daily_bars_are_not_available_before_regular_close(self) -> None:
        inputs, snapshot = self._inputs()
        before_close = snapshot.replace(hour=15, minute=59)
        row_before_close = generator.generate_row(inputs, before_close)
        row_at_close = generator.generate_row(inputs, snapshot)

        self.assertNotEqual(row_before_close["spy_return_1d"], row_at_close["spy_return_1d"])

    def test_sql_fetch_preserves_regular_session_intraday_bars(self) -> None:
        class FakeCursor:
            def __init__(self) -> None:
                self.calls: list[tuple[str, list[object] | None]] = []

            def execute(self, sql: str, params: list[object] | None = None) -> None:
                self.calls.append((sql, params))

            def fetchall(self) -> list[dict[str, object]]:
                return []

        cursor = FakeCursor()

        sql_runner.fetch_source_bars(cursor, source_schema="trading_data", source_table="m01_market_regime_data_acquisition")

        sql_text = cursor.calls[0][0]
        self.assertIn("lower(timeframe) IN ('1m', '1min', '1minute')", sql_text)
        self.assertNotIn("lower(timeframe) NOT IN", sql_text)
        self.assertIn("BETWEEN TIME '09:30' AND TIME '16:00'", sql_text)

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
                "input_frame": "1h",
                "prediction_horizon": "1D",
                "market_universe_ref": "layer_01_02_market_context_etf_universe",
                "spy_return_30m": 0.01,
                "qqq_spy_return_corr_20d": None,
            }
        ]

        sql_runner.write_feature_rows_sql(
            cursor,
            rows,
            target_schema="trading_data",
            target_table="m01_market_regime_feature_generation",
        )

        joined_sql = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn('CREATE TABLE IF NOT EXISTS "trading_data"."m01_market_regime_feature_generation"', joined_sql)
        self.assertIn('"feature_payload_json" JSONB NOT NULL DEFAULT', joined_sql)
        self.assertNotIn('ADD COLUMN IF NOT EXISTS "spy_return_30m" DOUBLE PRECISION', joined_sql)
        self.assertIn('PRIMARY KEY ("snapshot_time", "input_frame", "prediction_horizon", "market_universe_ref")', joined_sql)
        self.assertIn('ON CONFLICT ("snapshot_time", "input_frame", "prediction_horizon", "market_universe_ref") DO UPDATE SET', joined_sql)
        insert_params = cursor.calls[-1][1]
        self.assertIsNotNone(insert_params)
        self.assertEqual(insert_params[0], "2026-01-02T16:00:00-05:00")
        self.assertEqual(insert_params[1], "1h")
        self.assertEqual(insert_params[2], "1D")
        self.assertEqual(insert_params[3], "layer_01_02_market_context_etf_universe")
        self.assertIn('"spy_return_30m": 0.01', insert_params[4])

    def test_inferred_snapshots_use_one_hour_decision_surface(self) -> None:
        inputs, snapshot = self._inputs()
        inferred = generator.infer_snapshot_times(inputs)

        self.assertIn(snapshot, inferred)
        self.assertNotIn(snapshot - timedelta(minutes=30), inferred)
        self.assertNotIn(snapshot.replace(hour=9, minute=30), inferred)

    def test_generate_rows_can_emit_multiple_frame_horizon_identities(self) -> None:
        inputs, snapshot = self._inputs()

        rows = generator.generate_rows(inputs, snapshot_times=[snapshot], input_frames=("1min", "10min", "1h", "1D"))

        identities = {(row["input_frame"], row["prediction_horizon"]) for row in rows}
        self.assertEqual(
            identities,
            {
                ("1min", "10min"),
                ("10min", "1h"),
                ("1h", "1D"),
                ("1D", "1W"),
            },
        )

    def test_sql_snapshot_bounds_filter_lookback_context(self) -> None:
        snapshots = [
            "2026-03-31T16:00:00-04:00",
            "2026-04-01T10:00:00-04:00",
            "2026-04-30T16:00:00-04:00",
            "2026-05-01T10:00:00-04:00",
        ]

        self.assertEqual(
            sql_runner.filter_snapshot_times(
                snapshots,
                snapshot_start="2026-04-01T00:00:00-04:00",
                snapshot_end="2026-05-01T00:00:00-04:00",
            ),
            snapshots[1:3],
        )

    def test_feed_artifact_feature_bounds_include_lookback_but_preserve_month_window(self) -> None:
        source_start, snapshot_start, snapshot_end = from_feed_artifacts._feature_source_bounds("2026-04", lookback_days=10)

        self.assertEqual(source_start, "2026-03-22T00:00:00-04:00")
        self.assertEqual(snapshot_start, "2026-04-01T00:00:00-04:00")
        self.assertEqual(snapshot_end, "2026-04-30T23:59:59-04:00")
        with self.assertRaises(ValueError):
            from_feed_artifacts._feature_source_bounds("2026-04", lookback_days=-1)

    def test_feed_artifact_materializer_discovers_successful_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            saved = root / "monthly_backfill" / "alpaca_bars" / "SPY" / "2016-01" / "runs" / "run_1" / "saved"
            saved.mkdir(parents=True)
            csv_path = saved / "equity_bar.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["symbol", "timeframe", "timestamp", "bar_open", "bar_high", "bar_low", "bar_close", "bar_volume", "bar_vwap", "bar_trade_count"])
                writer.writerow(["SPY", "1Min", "2016-01-04T09:30:00-05:00", "200", "201", "199", "200.5", "1000", "200.25", "12"])
            receipt = root / "monthly_backfill" / "alpaca_bars" / "SPY" / "2016-01" / "completion_receipt.json"
            receipt.write_text(
                json.dumps(
                    {
                        "runs": [
                            {
                                "status": "succeeded",
                                "outputs": [str(csv_path)],
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            artifacts = from_feed_artifacts.discover_feed_artifacts(storage_root=root, month="2016-01")
            rows = from_feed_artifacts.read_equity_bar_rows(artifacts)

        self.assertEqual(artifacts, [csv_path])
        self.assertEqual(rows[0]["symbol"], "SPY")
        self.assertEqual(rows[0]["bar_close"], 200.5)
        self.assertEqual(rows[0]["bar_volume"], 1000)

    def test_materializer_writes_source_rows_with_market_regime_key(self) -> None:
        class FakeWriter:
            def __init__(self) -> None:
                self.calls = []

            def write_rows(self, *, table, columns, rows, key_columns):
                self.calls.append((table, tuple(columns), list(rows), tuple(key_columns)))
                return {"rows_written": len(rows)}

        writer = FakeWriter()
        rows = [{"symbol": "SPY", "timeframe": "1Min", "timestamp": "2016-01-04T09:30:00-05:00", "bar_open": 200, "bar_high": 201, "bar_low": 199, "bar_close": 200.5, "bar_volume": 1000, "bar_vwap": 200.25, "bar_trade_count": 12}]

        written = from_feed_artifacts.materialize_source_rows(rows, sql_writer=writer)

        self.assertEqual(written, 1)
        self.assertEqual(writer.calls[0][0], "m01_market_regime_data_acquisition")
        self.assertEqual(writer.calls[0][3], ("symbol", "timeframe", "timestamp"))

    @unittest.skipUnless(
        runtime_config.shared_path("main", "shared", "layer_01_02_market_context_etf_universe.csv").exists()
        and runtime_config.shared_path("main", "shared", "layer_01_02_market_context_relative_strength_combinations.csv").exists(),
        "shared market-regime CSVs are unavailable",
    )
    def test_current_shared_contract_generates_expected_width(self) -> None:
        inputs = generator.build_inputs(
            bar_rows=[],
            universe_rows=generator.read_csv_rows(runtime_config.shared_path("main", "shared", "layer_01_02_market_context_etf_universe.csv")),
            combination_rows=generator.read_csv_rows(runtime_config.shared_path("main", "shared", "layer_01_02_market_context_relative_strength_combinations.csv")),
        )

        row = generator.generate_row(inputs, datetime(2026, 1, 2, 16, 0, tzinfo=ET))

        self.assertEqual(inputs.market_state_symbols, sorted(inputs.market_state_symbols))
        self.assertNotIn("XLK", inputs.market_state_symbols)
        self.assertTrue(all(combo.model_layer == "layer_01_market_regime" for combo in generator._market_regime_combinations(inputs)))
        self.assertEqual(len(row), 748)
        self.assertFalse(any(key.startswith("ibit_") for key in row))
        self.assertFalse(any(key.startswith("etha_") for key in row))
        self.assertFalse(any(key.startswith("fsol_") for key in row))
        self.assertFalse(any(key.startswith("xlk_spy") for key in row))
        self.assertFalse(any(key.startswith("smh_xlk") for key in row))
        self.assertTrue(any(key.startswith("qqq_spy") for key in row))
        self.assertFalse(any(key.startswith("bkch_bitw") for key in row))
        self.assertFalse(any(key.startswith("shy_return_") for key in row))


if __name__ == "__main__":
    unittest.main()
