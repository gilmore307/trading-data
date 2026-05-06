from __future__ import annotations

import importlib
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
pipeline = importlib.import_module("data_source.source_03_target_state.pipeline")


class FakeWriter:
    def __init__(self) -> None:
        self.calls = []

    def write_rows(self, *, table, columns, rows, key_columns):
        self.calls.append({"table": table, "columns": list(columns), "rows": list(rows), "key_columns": list(key_columns)})
        return {"qualified_table": f"trading_data.{table}", "rows_written": len(rows)}


class Source03TargetStateTests(unittest.TestCase):
    def test_normalizes_candidate_mapped_bars_and_liquidity_without_model_facing_identity_claims(self) -> None:
        start = datetime(2026, 1, 2, 9, 30, tzinfo=ET).isoformat()
        task_key = {
            "task_id": "source03_unit",
            "source": "source_03_target_state",
            "params": {
                "timeframe": "1m",
                "target_candidates": [{"target_candidate_id": "tcand_001", "routing_symbol_ref": "AAPL"}],
                "bar_rows": [
                    {"symbol": "AAPL", "timestamp": start, "open": "100", "high": "101", "low": "99", "close": "100.5", "volume": "1000", "vwap": "100.25"}
                ],
                "liquidity_rows": [
                    {"symbol": "AAPL", "timestamp": start, "avg_bid": "100.45", "avg_ask": "100.55", "avg_spread": "0.10", "quote_count": "42"}
                ],
            },
            "output_root": "/tmp/source03_unit",
        }
        context = pipeline.build_context(task_key, "run_001")
        _, payload = pipeline.fetch(context)
        clean_result, cleaned = pipeline.clean(context, payload)

        self.assertEqual(clean_result.row_counts["source_03_target_state"], 1)
        row = cleaned.rows[0]
        self.assertEqual(row["target_candidate_id"], "tcand_001")
        self.assertEqual(row["symbol"], "AAPL")
        self.assertEqual(row["timeframe"], "1Min")
        self.assertAlmostEqual(row["dollar_volume"], 100500.0)
        self.assertAlmostEqual(row["spread_bps"], 0.10 / 100.5 * 10000)
        self.assertIn("source/audit/routing metadata", clean_result.details["identity_boundary"])

    def test_save_uses_accepted_table_and_candidate_key(self) -> None:
        writer = FakeWriter()
        context = pipeline.build_context({"task_id": "source03_unit", "source": "source_03_target_state", "params": {}, "output_root": "/tmp/source03_unit"}, "run_001")
        clean_result = pipeline.StepResult("succeeded", [], {"source_03_target_state": 1})
        payload = pipeline.CleanedPayload(rows=[{"target_candidate_id": "tcand_001", "timeframe": "1Min", "timestamp": "2026-01-02T09:30:00-05:00"}])
        result = pipeline.save(context, clean_result, payload, sql_writer=writer)

        self.assertEqual(result.references, ["trading_data.source_03_target_state"])
        self.assertEqual(writer.calls[0]["table"], "source_03_target_state")
        self.assertEqual(writer.calls[0]["key_columns"], ["target_candidate_id", "timeframe", "timestamp"])


if __name__ == "__main__":
    unittest.main()
