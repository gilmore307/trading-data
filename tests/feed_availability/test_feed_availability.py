from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from feed_availability.__main__ import main
from feed_availability.http import HttpResult
from feed_availability.probes import probe_bls
from feed_availability.report import ProbeResult, report_payload, write_report
from feed_availability.sanitize import sanitize_url, sanitize_value


class FakeClient:
    def post_json(self, url, *, payload, headers=None):
        self.payload = payload
        body = {
            "status": "REQUEST_SUCCEEDED",
            "Results": {
                "series": [
                    {
                        "seriesID": "CUUR0000SA0",
                        "data": [
                            {
                                "year": "2024",
                                "period": "M01",
                                "periodName": "January",
                                "value": "123.4",
                            }
                        ],
                    }
                ]
            },
        }
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(body).encode())


class SourceAvailabilityTests(unittest.TestCase):
    def test_sanitize_redacts_secret_like_keys(self):
        payload = {
            "api_key": "abc",
            "nested": {"Authorization": "Bearer abc", "ok": "value"},
            "long": "x" * 300,
        }
        sanitized = sanitize_value(payload)
        self.assertEqual(sanitized["api_key"], "[redacted]")
        self.assertEqual(sanitized["nested"]["Authorization"], "[redacted]")
        self.assertEqual(sanitized["nested"]["ok"], "value")
        self.assertTrue(sanitized["long"].endswith("...[truncated]"))

    def test_sanitize_url_redacts_secret_query_values(self):
        url = "https://example.test/api?api_key=abc&file_type=json&registrationkey=def&key=ghi"
        sanitized = sanitize_url(url)
        self.assertIn("api_key=%5Bredacted%5D", sanitized)
        self.assertIn("registrationkey=%5Bredacted%5D", sanitized)
        self.assertIn("key=%5Bredacted%5D", sanitized)
        self.assertIn("file_type=json", sanitized)

    def test_bls_probe_uses_mock_transport_and_sanitized_shape(self):
        with patch(
            "feed_availability.probes.load_secret_alias"
        ) as load_secret:
            load_secret.return_value.values = {}
            load_secret.return_value.alias = "bls"
            load_secret.return_value.path = Path("/root/secrets/bls.json")
            load_secret.return_value.present = False
            load_secret.return_value.keys_present = ()
            result = probe_bls(FakeClient(), "unused")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.http_status, 200)
        self.assertIn("Results", result.response_shape_keys)
        self.assertEqual(result.sample_rows[0]["period"], "M01")
        self.assertEqual(result.secret_alias["alias"], "bls")

    def test_report_shape_and_write_path(self):
        result = ProbeResult(
            feed="unit",
            status="ok",
            available=True,
            data_kind_candidates=["macro BLS data"],
            access="public",
            docs_url="https://example.test",
            response_shape_keys=["Results"],
            sample_rows=[{"value": "1"}],
        )
        payload = report_payload([result], mode="test")
        self.assertEqual(payload["report_type"], "feed_availability")
        self.assertEqual(payload["results"][0]["feed"], "unit")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_report([result], mode="test", report_root=Path(tmpdir))
            self.assertTrue(path.exists())
            written = json.loads(path.read_text())
            self.assertEqual(written["mode"], "test")

    def test_cli_list_mode_no_network(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--list", "--feed", "bls"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["feeds"][0]["feed"], "bls")
        self.assertIn("status_fields", payload)

    def test_cli_dry_run_no_write(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--dry-run", "--feed", "fred", "--no-write"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "dry-run")
        self.assertEqual(payload["results"][0]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
