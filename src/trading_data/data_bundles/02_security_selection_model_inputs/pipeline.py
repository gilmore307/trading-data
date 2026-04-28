"""Manager-facing 02 SecuritySelectionModel input bundle."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from trading_data.data_bundles.model_input_bundle import BundleSpec, run_bundle

from .stock_etf_exposure import derive as derive_stock_etf_exposure

SPEC = BundleSpec(bundle="02_security_selection_model_inputs", model_id="security_selection_model", output_name="02_security_selection_model_inputs")


def run(task_key: dict[str, Any], *, run_id: str):
    prepared = deepcopy(task_key)
    params = prepared.setdefault("params", {})
    if "stock_etf_exposure" in params:
        output_root = str(prepared.get("output_root") or f"storage/{prepared.get('task_id', SPEC.bundle + '_task')}")
        from pathlib import Path

        derived_dir = Path(output_root) / "runs" / run_id / "derived" / "stock_etf_exposure"
        stock_path, _row_count = derive_stock_etf_exposure(params["stock_etf_exposure"], output_dir=derived_dir)
        input_paths = params.setdefault("input_paths", {})
        input_paths["stock_etf_exposure"] = str(stock_path)
    return run_bundle(SPEC, prepared, run_id=run_id)
