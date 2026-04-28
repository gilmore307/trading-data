import csv
import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path

BUNDLES = {
    "01_market_regime_model_inputs": ["broad_market_bars", "sector_etf_bars"],
    "02_security_selection_model_inputs": ["stock_etf_exposure", "equity_bars"],
    "03_strategy_selection_model_inputs": ["selected_universe", "equity_bars"],
    "04_trade_quality_model_inputs": ["strategy_candidates", "market_context", "security_context"],
    "05_option_expression_model_inputs": ["option_chain_snapshot", "trade_quality_candidates"],
    "06_event_overlay_model_inputs": ["gdelt_articles", "trading_economics_calendar", "equity_abnormal_activity_events"],
    "07_portfolio_risk_model_inputs": ["option_expression_candidates"],
}


class ModelInputBundleTests(unittest.TestCase):
    def test_model_input_bundles_emit_point_in_time_manifest_csv(self):
        for bundle, required_roles in BUNDLES.items():
            with self.subTest(bundle=bundle), tempfile.TemporaryDirectory() as tmp:
                module = import_module(f"trading_data.data_bundles.{bundle}.pipeline")
                input_paths = {role: str(Path(tmp) / f"{role}.csv") for role in required_roles}
                for path in input_paths.values():
                    Path(path).write_text("placeholder\n", encoding="utf-8")
                task_key = {
                    "task_id": f"{bundle}_task_test",
                    "bundle": bundle,
                    "params": {"as_of_et": "2026-04-28T09:30:00-04:00", "input_paths": input_paths},
                    "output_root": str(Path(tmp) / "task"),
                }
                result = module.run(task_key, run_id="run")
                self.assertEqual(result.status, "succeeded")
                self.assertGreaterEqual(result.row_counts[bundle], len(required_roles))
                saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / f"{bundle}.csv"
                with saved.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertTrue(rows)
                self.assertEqual({row["bundle"] for row in rows}, {bundle})
                self.assertEqual({row["as_of_et"] for row in rows}, {"2026-04-28T09:30:00-04:00"})
                receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text(encoding="utf-8"))
                self.assertEqual(receipt["runs"][0]["status"], "succeeded")

    def test_missing_required_role_fails_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = import_module("trading_data.data_bundles.01_market_regime_model_inputs.pipeline")
            task_key = {
                "task_id": "01_market_regime_model_inputs_task_bad",
                "bundle": "01_market_regime_model_inputs",
                "params": {"as_of_et": "2026-04-28T09:30:00-04:00", "input_paths": {"broad_market_bars": "spy.csv"}},
                "output_root": str(Path(tmp) / "task"),
            }
            result = module.run(task_key, run_id="run")
            self.assertEqual(result.status, "failed")
            self.assertIn("missing required", result.details["error"]["message"])


if __name__ == "__main__":
    unittest.main()
