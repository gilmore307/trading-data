from __future__ import annotations

import unittest

from data_feature.m06_residual_event_governance_feature_generation.generator import generate_rows


class EventOverlayFeatureGeneratorTests(unittest.TestCase):
    def test_generates_deterministic_event_feature_payload(self) -> None:
        rows = generate_rows(
            [
                {
                    "event_id": "evt_1",
                    "canonical_event_id": "evt_1",
                    "dedup_status": "canonical",
                    "source_priority": "official_disclosure",
                    "event_time": "2026-05-08T13:30:00Z",
                    "available_time": "2026-05-08T13:31:00Z",
                    "information_role_type": "direct_observation",
                    "event_category_type": "company_disclosure",
                    "scope_type": "symbol",
                    "symbol": "AAPL",
                    "sector_type": "technology",
                    "title": "AAPL files update",
                    "summary": "Reviewed filing evidence.",
                    "source_name": "sec",
                    "reference_type": "url",
                    "reference": "https://example.test/filing",
                    "source_artifact_path": "/storage/sec/aapl-10q.html",
                }
            ],
            run_id="unit_run",
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["run_id"], "unit_run")
        self.assertEqual(row["source_run_ref"], "m06_residual_event_governance_data_acquisition")
        self.assertEqual(row["event_id"], "evt_1")
        self.assertEqual(row["canonical_event_id"], "evt_1")
        self.assertEqual(row["feature_payload_json"]["source_priority_rank"], 1)
        self.assertEqual(row["feature_payload_json"]["is_canonical_event"], 1)
        self.assertEqual(row["feature_payload_json"]["has_symbol_scope"], 1)
        self.assertEqual(row["feature_payload_json"]["has_source_artifact_path"], 1)
        self.assertTrue(row["feature_quality_diagnostics"]["has_required_fields"])

    def test_skips_rows_without_event_id_or_clock(self) -> None:
        rows = generate_rows([
            {"available_time": "2026-05-08T13:31:00Z"},
            {"event_id": "evt_missing_clock"},
        ])
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
