from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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
                "params": {"source": "bls", "series_ids": ["CUUR0000SA0"], "startyear": "2024", "endyear": "2024"},
                "output_root": str(Path(tmp) / "macro_data_task_test"),
            }
            result = run(task_key, run_id="macro_data_run_test", client=FakeMacroClient(payload))
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "macro_data_run_test" / "saved" / "macro_data_rows.jsonl"
            self.assertTrue(saved.exists())
            row = json.loads(saved.read_text().splitlines()[0])
            self.assertEqual(row["source"], "bls")
            self.assertEqual(row["series_id"], "CUUR0000SA0")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["row_counts"]["macro_data_rows"], 1)

    def test_census_array_shape_normalizes(self):
        payload = [["time", "cell_value"], ["2024", "12345"]]
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "macro_data_task_census",
                "bundle": "macro_data",
                "params": {"source": "census", "dataset": "timeseries/eits/marts", "get": "time,cell_value", "for": "us:*", "time": "2024"},
                "output_root": str(Path(tmp) / "macro_data_task_census"),
            }
            result = run(task_key, run_id="macro_data_run_census", client=FakeMacroClient(payload))
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["macro_data_rows"], 1)

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
