from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from trading_data.data_sources.macro_data.interfaces import MACRO_INTERFACES
from trading_data.data_sources.macro_data.pipeline import run
from trading_data.source_availability.http import HttpResult


class FakeMacroClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def post_json(self, url, *, payload, headers=None):
        self.requests.append(("POST", url, payload, headers))
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(self.payload).encode())

    def get(self, url, *, params=None, headers=None):
        self.requests.append(("GET", url, params, headers))
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(self.payload).encode())


class MacroDataPipelineTests(unittest.TestCase):
    def test_bls_fetch_clean_save_receipt(self):
        payload = {
            "Results": {
                "series": [
                    {
                        "seriesID": "CUUR0000SA0",
                        "data": [{"year": "2024", "period": "M01", "value": "309.685"}],
                    }
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "macro_data_task_test",
                "bundle": "macro_data",
                "params": {"source": "bls", "series_ids": ["CUUR0000SA0"], "startyear": "2024", "endyear": "2024", "release_time": "2024-02-13T08:30:00-05:00", "effective_until": "2024-03-12T08:30:00-04:00"},
                "output_root": str(Path(tmp) / "macro_data_task_test"),
            }
            result = run(task_key, run_id="macro_data_run_test", client=FakeMacroClient(payload))
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "macro_data_run_test" / "saved" / "macro_release.csv"
            self.assertTrue(saved.exists())
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["metric"], "CUUR0000SA0")
            self.assertEqual(row["release_time"], "2024-02-13T08:30:00-05:00")
            self.assertEqual(row["effective_until"], "2024-03-12T08:30:00-04:00")
            self.assertEqual(row["value"], "309.685")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["row_counts"]["macro_release"], 1)

    def test_census_array_shape_normalizes(self):
        payload = [["time", "cell_value"], ["2024", "12345"]]
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "macro_data_task_census",
                "bundle": "macro_data",
                "params": {"source": "census", "dataset": "timeseries/eits/marts", "get": "time,cell_value", "for": "us:*", "time": "2024", "metric": "retail_sales", "release_time": "2024-02-15T08:30:00-05:00"},
                "output_root": str(Path(tmp) / "macro_data_task_census"),
            }
            result = run(task_key, run_id="macro_data_run_census", client=FakeMacroClient(payload))
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["macro_release"], 1)

    def test_data_kind_defaults_resolve_to_provider_params(self):
        payload = {"Results": {"series": [{"seriesID": "CUUR0000SA0", "data": [{"value": "309.685"}]}]}}
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "macro_data_task_kind_default",
                "bundle": "macro_data",
                "params": {"data_kind": "macro_bls_cpi"},
                "output_root": str(Path(tmp) / "macro_data_task_kind_default"),
            }
            result = run(task_key, run_id="macro_data_run_kind_default", client=FakeMacroClient(payload))
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["macro_release"], 1)

    def test_all_macro_interfaces_have_source_and_release_defaults_or_adapter_note(self):
        for key, interface in MACRO_INTERFACES.items():
            self.assertTrue(interface.source)
            if interface.source != "official_macro_release_calendar":
                self.assertIn("release_time", interface.default_params, key)

    def test_unsupported_source_writes_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "macro_data_task_bad",
                "bundle": "macro_data",
                "params": {"source": "not_a_source"},
                "output_root": str(Path(tmp) / "macro_data_task_bad"),
            }
            result = run(task_key, run_id="macro_data_run_bad", client=FakeMacroClient({}))
            self.assertEqual(result.status, "failed")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["error"]["type"], "MacroDataError")


if __name__ == "__main__":
    unittest.main()
