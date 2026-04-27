from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from trading_data.source_availability.http import HttpResult
from trading_data.source_interfaces.__main__ import main
from trading_data.data_sources.macro_data.interfaces import MACRO_INTERFACES
from trading_data.source_interfaces.catalog import INTERFACES
from trading_data.source_interfaces.probes import probe_interface


class FakeClient:
    def get(self, url, *, params=None, headers=None):
        if "okx" in url:
            return HttpResult(url=url, status=200, headers={}, body=json.dumps({"code": "0", "data": [["1", "2"]]}).encode())
        if "alpaca" in url and "bars" in url:
            return HttpResult(url=url, status=200, headers={}, body=json.dumps({"bars": [{"t": "2024-01-02T00:00:00Z", "c": 1}]}).encode())
        return HttpResult(url=url, status=200, headers={}, body=json.dumps({"ok": True}).encode())


class SourceInterfaceTests(unittest.TestCase):
    def test_catalog_has_required_provider_kinds(self):
        for key in ["equity_bar", "equity_trade", "equity_quote", "equity_news", "crypto_bar", "crypto_trade", "crypto_quote", "crypto_order_book", "option_trade", "option_quote", "sec_submission"]:
            self.assertIn(key, INTERFACES)

    def test_catalog_has_all_macro_interfaces(self):
        self.assertGreaterEqual(len(MACRO_INTERFACES), 30)
        for key in MACRO_INTERFACES:
            self.assertIn(key, INTERFACES)
            self.assertEqual(INTERFACES[key].bundle, "macro_data")

    def test_cli_list_no_network(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(["--list", "--source", "okx"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["interfaces"])
        self.assertTrue(all(item["source"] == "okx" for item in payload["interfaces"]))

    def test_okx_probe_uses_data_path(self):
        result = probe_interface(INTERFACES["crypto_bar"], FakeClient(), sec_user_agent="test")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.sample_rows[0], ["1", "2"])

    def test_alpaca_probe_sanitizes_secret_summary(self):
        class Secret:
            alias = "alpaca"
            path = "/root/secrets/alpaca.json"
            present = True
            keys_present = ("api_key", "secret_key")
            values = {"api_key": "key", "secret_key": "secret", "endpoint": "https://data.alpaca.markets"}
        with patch("trading_data.source_interfaces.probes.load_secret_alias", return_value=Secret()):
            result = probe_interface(INTERFACES["equity_bar"], FakeClient(), sec_user_agent="test")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.secret_alias["keys_present"], ["api_key", "secret_key"])


if __name__ == "__main__":
    unittest.main()
