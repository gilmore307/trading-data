"""Manager-facing strategy_selection_model_inputs bundle."""
from __future__ import annotations

from trading_data.data_bundles.model_input_bundle import BundleSpec, run_bundle

SPEC = BundleSpec(bundle="layer03_strategy_selection_model_inputs", model_id="strategy_selection_model", output_name="layer03_strategy_selection_model_inputs")

def run(task_key: dict, *, run_id: str):
    return run_bundle(SPEC, task_key, run_id=run_id)
