"""Manager-facing trade_quality_model_inputs bundle."""
from __future__ import annotations

from trading_data.data_bundles.model_input_bundle import BundleSpec, run_bundle
from trading_data.storage.sql import SqlTableWriter

SPEC = BundleSpec(bundle="04_trade_quality_model_inputs", model_id="trade_quality_model", output_name="04_trade_quality_model_inputs")

def run(task_key: dict, *, run_id: str, sql_writer: SqlTableWriter | None = None):
    return run_bundle(SPEC, task_key, run_id=run_id, sql_writer=sql_writer)
