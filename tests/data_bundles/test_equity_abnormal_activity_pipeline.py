import csv
import importlib
import json
import tempfile
import unittest
from pathlib import Path

pipeline = importlib.import_module(
    "trading_data.data_bundles.07_event_overlay_model_inputs.equity_abnormal_activity.pipeline"
)
detect_events = pipeline.detect_events
run = pipeline.run


def _bar(symbol: str, idx: int, close: float, volume: int, open_: float | None = None) -> dict[str, str]:
    return {
        "symbol": symbol,
        "timeframe": "1Min",
        "timestamp": f"2026-04-24T09:{30 + idx:02d}:00-04:00",
        "open": str(open_ if open_ is not None else close),
        "high": str(close),
        "low": str(close),
        "close": str(close),
        "volume": str(volume),
        "vwap": str(close),
        "trade_count": "10",
    }


class EquityAbnormalActivityPipelineTests(unittest.TestCase):
    def test_detects_return_volume_and_gap_events(self):
        bars = [_bar("NVDA", i, 100 + i * 0.1, 1000 + i) for i in range(10)]
        bars.append(_bar("NVDA", 10, 120, 10000, open_=118))
        events = detect_events(bars=bars, lookback_intervals=5, min_abs_return_zscore=3.0, min_volume_zscore=3.0, min_abs_gap_pct=0.04)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["symbol"], "NVDA")
        self.assertIn("return_zscore", event["abnormal_activity_type"])
        self.assertIn("volume_spike", event["abnormal_activity_type"])
        self.assertIn("gap", event["abnormal_activity_type"])
        self.assertEqual(event["event_type"], "equity_abnormal_activity_event")

    def test_pipeline_saves_event_csv_from_saved_bar_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            bars_path = Path(tmp) / "equity_bar.csv"
            rows = [_bar("NVDA", i, 100 + i * 0.1, 1000 + i) for i in range(10)] + [_bar("NVDA", 10, 120, 10000, open_=118)]
            with bars_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            task_key = {
                "task_id": "equity_abnormal_activity_task_test",
                "bundle": "07_event_overlay_model_inputs.equity_abnormal_activity",
                "params": {
                    "bars_csv_path": str(bars_path),
                    "lookback_intervals": 5,
                    "min_abs_return_zscore": 3.0,
                    "min_volume_zscore": 3.0,
                    "min_abs_gap_pct": 0.04,
                },
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["equity_abnormal_activity_event"], 1)
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "equity_abnormal_activity_event.csv"
            with saved.open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["source_type"], "alpaca_equity_market_data")
            self.assertIn("alpaca_bars:NVDA", row["source_references"])
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["runs"][0]["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
