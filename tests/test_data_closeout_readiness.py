from __future__ import annotations

import importlib
import json
import unittest
from pathlib import Path

from data_source.config import load_source_config

holdings_pipeline = importlib.import_module("data_source.source_02_target_candidate_holdings.pipeline")
equity_activity_pipeline = importlib.import_module("data_source.source_04_event_overlay.equity_abnormal_activity.pipeline")


class DataCloseoutReadinessTests(unittest.TestCase):
    def test_target_candidate_holdings_default_available_time_is_next_session_open(self) -> None:
        self.assertEqual(
            holdings_pipeline._available_time({}, {}, "2026-05-07"),
            "2026-05-08T09:30:00-04:00",
        )
        self.assertEqual(
            holdings_pipeline._available_time({}, {}, "2026-05-08"),
            "2026-05-11T09:30:00-04:00",
        )

    def test_target_candidate_holdings_explicit_available_time_wins(self) -> None:
        self.assertEqual(
            holdings_pipeline._available_time({"available_time": "2026-05-07T12:00:00-04:00"}, {}, "2026-05-07"),
            "2026-05-07T12:00:00-04:00",
        )
        self.assertEqual(
            holdings_pipeline._available_time({}, {"available_time": "2026-05-07T16:30:00-04:00"}, "2026-05-07"),
            "2026-05-07T16:30:00-04:00",
        )

    def test_equity_abnormal_activity_default_standard_is_conservative(self) -> None:
        config = json.loads(Path("src/data_source/source_04_event_overlay/equity_abnormal_activity/config.json").read_text())

        self.assertEqual(config["model_standard"], "equity_abnormal_activity_conservative")
        self.assertEqual(config["calibration_status"], "conservative_fixture_default_not_production_calibrated")
        self.assertGreaterEqual(config["min_abs_return_zscore"], 3.0)
        self.assertGreaterEqual(config["min_volume_zscore"], 3.0)

    def test_source_config_loader_supports_nested_packaged_config(self) -> None:
        config = load_source_config("source_04_event_overlay/equity_abnormal_activity")

        self.assertEqual(config["model_standard"], "equity_abnormal_activity_conservative")

    def test_equity_abnormal_activity_events_carry_model_standard(self) -> None:
        rows = []
        close = 100.0
        for index in range(1, 24):
            ts = f"2026-05-07T09:{30 + index:02d}:00-04:00"
            next_close = close * 1.001
            rows.append({"symbol": "ABC", "timestamp": ts, "timeframe": "1Min", "open": str(close), "close": str(next_close), "volume": "1000"})
            close = next_close
        rows.append({"symbol": "ABC", "timestamp": "2026-05-07T09:54:00-04:00", "timeframe": "1Min", "open": str(close * 1.05), "close": str(close * 1.08), "volume": "8000"})

        events = equity_activity_pipeline.detect_events(
            bars=rows,
            lookback_intervals=20,
            min_abs_return_zscore=3.0,
            min_volume_zscore=3.0,
            min_abs_relative_strength_zscore=3.0,
            min_abs_gap_pct=0.04,
            min_liquidity_spread_zscore=3.0,
            model_standard="equity_abnormal_activity_conservative",
        )

        self.assertTrue(events)
        taxonomy = json.loads(events[-1]["taxonomy_context"])
        self.assertEqual(taxonomy["detector"], "equity_abnormal_activity_conservative")


if __name__ == "__main__":
    unittest.main()
