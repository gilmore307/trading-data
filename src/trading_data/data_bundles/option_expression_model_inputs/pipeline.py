"""Manager-facing option_expression_model_inputs bundle."""
from __future__ import annotations

from trading_data.data_bundles.model_input_bundle import BundleSpec, run_bundle

SPEC = BundleSpec(bundle="option_expression_model_inputs", model_id="option_expression_model", output_name="option_expression_model_inputs")

def run(task_key: dict, *, run_id: str):
    return run_bundle(SPEC, task_key, run_id=run_id)
