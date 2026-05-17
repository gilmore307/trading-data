import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_DIR = Path("schemas")
FIXTURE_DIR = Path("tests/fixtures/contracts")


class ContractSchemaTests(unittest.TestCase):
    def test_schema_and_fixture_contract_types_match_and_validate(self):
        for schema_path in sorted(SCHEMA_DIR.glob("*.schema.json")):
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            contract_type = schema["title"]
            fixture_path = FIXTURE_DIR / f"{contract_type}.json"
            self.assertTrue(fixture_path.exists(), f"missing fixture for {contract_type}")
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            self.assertEqual(fixture.get("contract_type"), contract_type)
            Draft202012Validator(schema).validate(fixture)

    def test_task_key_requires_feed_or_source_route(self):
        fixture = json.loads((FIXTURE_DIR / "task_key.json").read_text(encoding="utf-8"))
        self.assertTrue(bool(fixture.get("feed")) ^ bool(fixture.get("source")))

    def test_receipt_fixture_contains_run_scoped_evidence_fields(self):
        fixture = json.loads((FIXTURE_DIR / "completion_receipt.json").read_text(encoding="utf-8"))
        run = fixture["runs"][0]
        self.assertIn("run_id", run)
        self.assertIn("output_dir", run)
        self.assertIn("steps", run)


if __name__ == "__main__":
    unittest.main()
