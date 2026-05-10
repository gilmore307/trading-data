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
generator = importlib.import_module("data_feature.feature_02_sector_context.generator")
sql_runner = importlib.import_module("data_feature.feature_02_sector_context.sql")
from_feed_artifacts = importlib.import_module("data_feature.feature_02_sector_context.from_feed_artifacts")


def _bar(symbol: str, day: date, close: float, *, timeframe: str = "1Day") -> dict[str, str]:
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "timestamp": datetime.combine(day, datetime.min.time(), tzinfo=ET).isoformat(),
        "bar_open": str(close * 0.99),
        "bar_high": str(close * 1.02),
        "bar_low": str(close * 0.98),
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


class SectorContextFeatureGeneratorTests(unittest.TestCase):
    def _inputs(self):
        universe = [
            {"symbol": "SPY", "universe_type": "market_state_etf", "model_layer": "layer_01_market_regime"},
            {"symbol": "QQQ", "universe_type": "market_state_etf", "model_layer": "layer_01_market_regime"},
            {"symbol": "XLK", "universe_type": "sector_observation_etf", "model_layer": "layer_02_sector_context"},
            {"symbol": "XLP", "universe_type": "sector_observation_etf", "model_layer": "layer_02_sector_context"},
            {"symbol": "SMH", "universe_type": "sector_observation_etf", "model_layer": "layer_02_sector_context"},
        ]
        combinations = [
            {
                "combination_id": "qqq_spy",
                "combination_type": "primary",
                "model_layer": "layer_01_market_regime",
                "numerator_symbol": "QQQ",
                "denominator_symbol": "SPY",
                "feature_bar_grain": "30m",
            },
            {
                "combination_id": "xlk_spy",
                "combination_type": "sector_rotation",
                "model_layer": "layer_02_sector_context",
                "numerator_symbol": "XLK",
                "denominator_symbol": "SPY",
                "feature_bar_grain": "30m",
            },
            {
                "combination_id": "smh_xlk",
                "combination_type": "daily_context",
                "model_layer": "layer_02_sector_context",
                "numerator_symbol": "SMH",
                "denominator_symbol": "XLK",
                "feature_bar_grain": "1d",
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
            smh_close = 110 + index * 1.4 + math.sin(index / 6)
            for symbol, close in {"SPY": spy_close, "QQQ": qqq_close, "XLK": xlk_close, "XLP": xlp_close, "SMH": smh_close}.items():
                bars.append(_bar(symbol, day, close))
        snapshot = datetime.combine(start + timedelta(days=269), datetime.min.time(), tzinfo=ET).replace(hour=16)
        bars.extend(
            [
                _intraday_bar("SPY", snapshot - timedelta(minutes=30), 369.0),
                _intraday_bar("SPY", snapshot, 370.0),
                _intraday_bar("XLK", snapshot - timedelta(minutes=30), 94.0),
                _intraday_bar("XLK", snapshot, 95.0),
            ]
        )
        return generator.build_inputs(bar_rows=bars, universe_rows=universe, combination_rows=combinations), snapshot

    def test_intraday_only_symbols_still_get_daily_derived_evidence(self) -> None:
        inputs, snapshot = self._inputs()
        # Mimic the real provider split where 30m rotation ETFs do not always
        # have explicit 1Day rows in the source table.
        bars = [bar for symbol, rows in inputs.bars_by_symbol.items() for bar in rows if not (symbol in {"SPY", "XLK"} and bar.timeframe == "1Day")]
        for symbol in ("SPY", "XLK"):
            for daily_bar in inputs.bars_by_symbol[symbol][-80:]:
                close_time = daily_bar.available_time.replace(hour=16, minute=0, second=0, microsecond=0)
                bars.append(
                    generator.market_features.Bar(
                        symbol=symbol,
                        timeframe="30Min",
                        timestamp=close_time,
                        available_time=close_time,
                        open=daily_bar.open,
                        high=daily_bar.high,
                        low=daily_bar.low,
                        close=daily_bar.close,
                        volume=daily_bar.volume,
                    )
                )
        fallback_inputs = generator.MarketRegimeInputs(
            bars_by_symbol={symbol: sorted([bar for bar in bars if bar.symbol == symbol], key=lambda item: (item.available_time, item.timestamp)) for symbol in {bar.symbol for bar in bars}},
            market_state_symbols=inputs.market_state_symbols,
            sector_observation_symbols=inputs.sector_observation_symbols,
            combinations=inputs.combinations,
        )

        rows = generator.generate_rows(fallback_inputs, [snapshot])
        xlk_row = next(row for row in rows if row["rotation_pair_id"] == "xlk_spy")

        self.assertIsNotNone(xlk_row["relative_strength_distance_to_ma20"])
        self.assertIsNotNone(xlk_row["relative_strength_return_corr_20d"])

    def test_generates_sector_rotation_candidate_rows(self) -> None:
        inputs, snapshot = self._inputs()

        rows = generator.generate_rows(inputs, [snapshot])

        self.assertEqual(len(rows), 3)
        pair_ids = {row["rotation_pair_id"] for row in rows}
        self.assertEqual(pair_ids, {"sector_observation_breadth", "xlk_spy", "smh_xlk"})
        self.assertNotIn("qqq_spy", pair_ids)

        summary_row = next(row for row in rows if row["rotation_pair_id"] == "sector_observation_breadth")
        self.assertEqual(summary_row["candidate_symbol"], "SECTOR_OBSERVATION_UNIVERSE")
        self.assertEqual(summary_row["candidate_type"], "sector_rotation_summary")
        self.assertIn("sector_observation_positive_return_1d_pct", summary_row)
        self.assertIn("sector_observation_return_20d_dispersion", summary_row)

        xlk_row = next(row for row in rows if row["rotation_pair_id"] == "xlk_spy")
        self.assertEqual(xlk_row["candidate_symbol"], "XLK")
        self.assertEqual(xlk_row["candidate_type"], "sector_industry_etf")
        self.assertEqual(xlk_row["comparison_symbol"], "SPY")
        self.assertEqual(xlk_row["rotation_pair_type"], "sector_rotation")
        self.assertAlmostEqual(xlk_row["relative_strength_return_30m"], math.log((95.0 / 370.0) / (94.0 / 369.0)))
        self.assertIn("relative_strength_distance_to_ma20", xlk_row)
        self.assertNotIn("relative_strength_ma20", xlk_row)
        self.assertIn("relative_strength_return_corr_20d", xlk_row)

        smh_row = next(row for row in rows if row["rotation_pair_id"] == "smh_xlk")
        self.assertEqual(smh_row["candidate_symbol"], "SMH")
        self.assertEqual(smh_row["comparison_symbol"], "XLK")
        self.assertEqual(smh_row["rotation_pair_type"], "daily_context")
        self.assertIn("relative_strength_return_1d", smh_row)

    def test_sql_fetch_downsamples_one_minute_bars_to_decision_surface(self) -> None:
        class FakeCursor:
            def __init__(self) -> None:
                self.calls: list[tuple[str, list[object] | None]] = []

            def execute(self, sql: str, params: list[object] | None = None) -> None:
                self.calls.append((sql, params))

            def fetchall(self) -> list[dict[str, object]]:
                return []

        cursor = FakeCursor()

        sql_runner.fetch_source_bars(cursor, source_schema="trading_data", source_table="source_01_market_regime")

        sql_text = cursor.calls[0][0]
        self.assertIn("lower(timeframe) NOT IN ('1m', '1min', '1minute')", sql_text)
        self.assertIn("EXTRACT(MINUTE FROM timestamp AT TIME ZONE 'America/New_York') IN (0, 30)", sql_text)
        self.assertIn("BETWEEN TIME '09:30' AND TIME '16:00'", sql_text)

    def test_sql_writer_persists_candidate_comparison_rows(self) -> None:
        class FakeCursor:
            def __init__(self) -> None:
                self.calls: list[tuple[str, list[object] | None]] = []

            def execute(self, sql: str, params: list[object] | None = None) -> None:
                self.calls.append((sql, params))

        cursor = FakeCursor()
        rows = [
            {
                "snapshot_time": "2026-01-02T16:00:00-05:00",
                "candidate_symbol": "XLK",
                "candidate_type": "sector_industry_etf",
                "comparison_symbol": "SPY",
                "rotation_pair_id": "xlk_spy",
                "rotation_pair_type": "sector_rotation",
                "feature_bar_grain": "30m",
                "relative_strength_return": 0.01,
            }
        ]

        sql_runner.write_feature_rows_sql(cursor, rows, target_schema="trading_data", target_table="feature_02_sector_context")

        joined_sql = "\n".join(sql for sql, _params in cursor.calls)
        self.assertIn('CREATE TABLE IF NOT EXISTS "trading_data"."feature_02_sector_context"', joined_sql)
        self.assertIn('PRIMARY KEY ("snapshot_time", "candidate_symbol", "comparison_symbol", "rotation_pair_id")', joined_sql)
        self.assertIn('ON CONFLICT ("snapshot_time", "candidate_symbol", "comparison_symbol", "rotation_pair_id") DO UPDATE SET', joined_sql)
        insert_params = cursor.calls[-1][1]
        self.assertIsNotNone(insert_params)
        self.assertEqual(insert_params[:7], ["2026-01-02T16:00:00-05:00", "XLK", "sector_industry_etf", "SPY", "xlk_spy", "sector_rotation", "30m"])
        payload = json.loads(insert_params[7])  # type: ignore[index]
        self.assertEqual(payload, {"relative_strength_return": 0.01})

    def test_feed_artifact_materializer_reads_existing_layer_two_outputs_without_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            saved = root / "monthly_backfill_v1" / "alpaca_bars" / "XLK" / "2016-01" / "runs" / "run_1" / "saved"
            saved.mkdir(parents=True)
            csv_path = saved / "equity_bar.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["symbol", "timeframe", "timestamp", "bar_open", "bar_high", "bar_low", "bar_close", "bar_volume", "bar_vwap", "bar_trade_count"])
                writer.writerow(["XLK", "30Min", "2016-01-04T09:30:00-05:00", "40", "41", "39", "40.5", "1000", "40.25", "12"])
            receipt = root / "monthly_backfill_v1" / "alpaca_bars" / "XLK" / "2016-01" / "completion_receipt.json"
            receipt.write_text(json.dumps({"runs": [{"status": "succeeded", "outputs": [str(csv_path)]}]}) + "\n", encoding="utf-8")

            summary = from_feed_artifacts.run_from_feed_artifacts(storage_root=root, month="2016-01", dry_run=True)

        self.assertEqual(summary.contract_type, "feature_02_sector_context_from_feed_artifacts_v1")
        self.assertEqual(summary.artifact_count, 1)
        self.assertEqual(summary.source_rows_found, 1)
        self.assertEqual(summary.source_rows_written, 0)
        self.assertEqual(summary.feature_rows_written, 0)
        self.assertEqual(summary.provider_calls, 0)
        self.assertFalse(summary.model_activation_performed)
        self.assertFalse(summary.broker_execution_performed)

    @unittest.skipUnless(
        Path("/root/projects/trading-storage/main/shared/market_regime_etf_universe.csv").exists()
        and Path("/root/projects/trading-storage/main/shared/market_regime_relative_strength_combinations.csv").exists(),
        "shared market-regime CSVs are unavailable",
    )
    def test_current_shared_contract_generates_expected_rotation_rows(self) -> None:
        inputs = generator.build_inputs(
            bar_rows=[],
            universe_rows=generator.read_csv_rows("/root/projects/trading-storage/main/shared/market_regime_etf_universe.csv"),
            combination_rows=generator.read_csv_rows("/root/projects/trading-storage/main/shared/market_regime_relative_strength_combinations.csv"),
        )

        rows = generator.generate_rows(inputs, [datetime(2026, 1, 2, 16, 0, tzinfo=ET)])

        self.assertTrue(all(combo.model_layer == "layer_02_sector_context" for combo in generator.rotation_combinations(inputs)))
        self.assertEqual(len(rows), 32)
        self.assertEqual({row["rotation_pair_type"] for row in rows}, {"sector_rotation_summary", "sector_rotation", "daily_context"})
        self.assertIn("sector_observation_breadth", {row["rotation_pair_id"] for row in rows})
        pair_ids = {row["rotation_pair_id"] for row in rows}
        self.assertIn("xlk_spy", pair_ids)
        self.assertIn("smh_xlk", pair_ids)
        self.assertIn("bkch_bitw", pair_ids)
        self.assertEqual(sum(1 for row in rows if row["rotation_pair_type"] == "sector_rotation"), 18)


if __name__ == "__main__":
    unittest.main()
