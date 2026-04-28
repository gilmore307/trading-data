import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path

from trading_data.source_availability.http import HttpResult

BUNDLES = {
    "06_event_overlay_model_inputs": ["gdelt_articles", "trading_economics_calendar", "equity_abnormal_activity_events"],
    "07_portfolio_risk_model_inputs": ["option_expression_candidates"],
}


class FakeBarsClient:
    def get(self, url, *, params=None, headers=None):
        symbol = url.rstrip("/").split("/")[-2]
        timeframe = (params or {}).get("timeframe", "1Day")
        payload = {"bars": [{"t": "2026-04-24T13:30:00Z", "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 1000, "vw": 100.25, "n": 10}]}
        if timeframe == "30Min":
            payload["bars"][0]["t"] = "2026-04-24T14:00:00Z"
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(payload).encode())


class FakeStrategySelectionClient:
    def get(self, url, *, params=None, headers=None):
        if url.endswith("/bars"):
            payload = {"bars": [{"t": "2026-04-24T13:30:00Z", "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 1000, "vw": 100.25, "n": 10}]}
        elif url.endswith("/trades"):
            payload = {"trades": [{"t": "2026-04-24T13:30:10Z", "p": 100.5, "s": 100}, {"t": "2026-04-24T13:30:40Z", "p": 100.7, "s": 200}]}
        elif url.endswith("/quotes"):
            payload = {"quotes": [{"t": "2026-04-24T13:30:05Z", "bp": 100.4, "ap": 100.6, "bs": 10, "as": 12}, {"t": "2026-04-24T13:30:45Z", "bp": 100.5, "ap": 100.7, "bs": 20, "as": 22}]}
        else:
            payload = {}
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(payload).encode())


class FakeThetaDataClient:
    def get(self, url, *, params=None, headers=None):
        if url.endswith("/snapshot/quote"):
            payload = {"response": [{"contract": {"symbol": "AAPL", "expiration": "2026-05-15", "right": "CALL", "strike": 270.0}, "data": [{"timestamp": "2026-04-24T09:30:02.260", "bid": 1.15, "ask": 1.25, "bid_size": 12, "ask_size": 15}]}]}
        elif url.endswith("/snapshot/greeks/implied_volatility"):
            payload = {"response": [{"contract": {"symbol": "AAPL", "expiration": "2026-05-15", "right": "CALL", "strike": 270.0}, "data": [{"timestamp": "2026-04-24T09:30:02.260", "implied_vol": 0.64, "iv_error": 0.0, "underlying_price": 271.95, "underlying_timestamp": "2026-04-24T13:30:02.260"}]}]}
        elif url.endswith("/snapshot/greeks/first_order"):
            payload = {"response": [{"contract": {"symbol": "AAPL", "expiration": "2026-05-15", "right": "CALL", "strike": 270.0}, "data": [{"timestamp": "2026-04-24T09:30:02.260", "delta": 0.52, "theta": -0.11, "vega": 18.2, "rho": 4.3}]}]}
        else:
            payload = {"response": []}
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(payload).encode())


class FakeSqlWriter:
    def __init__(self):
        self.calls = []

    def write_rows(self, *, table, columns, rows, key_columns):
        self.calls.append({"table": table, "columns": list(columns), "rows": list(rows), "key_columns": list(key_columns)})
        return {"storage_target_id": "test_postgres", "driver": "postgresql", "schema": "model_inputs", "table": table, "qualified_table": f"model_inputs.{table}", "rows_written": len(rows)}


class Secret:
    alias = "alpaca"
    path = Path("/root/secrets/alpaca.json")
    present = True
    keys_present = ("api_key", "secret_key")
    values = {"api_key": "k", "secret_key": "s", "data_endpoint": "https://data.alpaca.markets"}


class ModelInputBundleTests(unittest.TestCase):
    def test_market_regime_bundle_fetches_universe_bars_as_one_sql_long_table(self):
        module = import_module("trading_data.data_bundles.01_market_regime_model_inputs.pipeline")
        old_load_secret = module.load_secret_alias
        module.load_secret_alias = lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                universe_path = Path(tmp) / "market_etf_universe.csv"
                universe_path.write_text(
                    "symbol,universe_type,exposure_type,bar_grain,fund_name,issuer_name\n"
                    "SPY,broad_market,core,1d,SPDR S&P 500 ETF,State Street\n"
                    "BITW,sector_observation_etf,crypto_beta,30m,Bitwise 10 Crypto Index ETF,Bitwise\n",
                    encoding="utf-8",
                )
                task_key = {
                    "task_id": "01_market_regime_model_inputs_task_test",
                    "bundle": "01_market_regime_model_inputs",
                    "params": {"start": "2026-04-24", "end": "2026-04-25", "market_etf_universe_path": str(universe_path), "max_pages": 2},
                    "output_root": str(Path(tmp) / "task"),
                }
                writer = FakeSqlWriter()
                result = module.run(task_key, run_id="run", client=FakeBarsClient(), sql_writer=writer)
                self.assertEqual(result.status, "succeeded")
                self.assertEqual(result.row_counts["market_regime_etf_bar"], 2)
                self.assertFalse((Path(task_key["output_root"]) / "runs" / "run" / "saved" / "01_market_regime_model_inputs.csv").exists())
                self.assertEqual(result.references, [str(Path(task_key["output_root"]) / "completion_receipt.json"), "model_inputs.market_regime_etf_bar"])
                self.assertEqual(len(writer.calls), 1)
                call = writer.calls[0]
                self.assertEqual(call["table"], "market_regime_etf_bar")
                self.assertEqual(call["key_columns"], ["run_id", "symbol", "timeframe", "timestamp"])
                rows = sorted(call["rows"], key=lambda row: row["symbol"])
                self.assertEqual(len(rows), 2)
                self.assertEqual({row["symbol"]: row["timeframe"] for row in rows}, {"BITW": "30Min", "SPY": "1Day"})
                self.assertEqual({row["run_id"] for row in rows}, {"run"})
                self.assertEqual(call["columns"], ["run_id", "task_id", "symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume", "vwap", "trade_count", "created_at"])
        finally:
            module.load_secret_alias = old_load_secret

    def test_strategy_selection_bundle_writes_bar_liquidity_sql_rows(self):
        module = import_module("trading_data.data_bundles.03_strategy_selection_model_inputs.pipeline")
        old_load_secret = module.load_secret_alias
        module.load_secret_alias = lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                task_key = {
                    "task_id": "03_strategy_selection_model_inputs_task_test",
                    "bundle": "03_strategy_selection_model_inputs",
                    "params": {"start": "2026-04-24T13:30:00Z", "end": "2026-04-24T13:31:00Z", "symbols": ["NVDA"]},
                    "output_root": str(Path(tmp) / "task"),
                }
                writer = FakeSqlWriter()
                result = module.run(task_key, run_id="run", client=FakeStrategySelectionClient(), sql_writer=writer)
                self.assertEqual(result.status, "succeeded")
                self.assertEqual(result.row_counts["strategy_selection_symbol_bar_liquidity"], 1)
                call = writer.calls[0]
                self.assertEqual(call["table"], "strategy_selection_symbol_bar_liquidity")
                self.assertEqual(call["key_columns"], ["run_id", "symbol", "timeframe", "timestamp"])
                row = call["rows"][0]
                self.assertEqual(row["symbol"], "NVDA")
                self.assertEqual(row["timeframe"], "1Min")
                self.assertEqual(row["timestamp"], "2026-04-24T09:30:00-04:00")
                self.assertEqual(row["dollar_volume"], 100500.0)
                self.assertAlmostEqual(row["avg_spread"], 0.2)
                self.assertAlmostEqual(row["spread_bps"], 19.890601690701146)
                self.assertNotIn("created_at", row)
        finally:
            module.load_secret_alias = old_load_secret

    def test_option_expression_bundle_writes_option_snapshot_sql_row(self):
        module = import_module("trading_data.data_bundles.05_option_expression_model_inputs.pipeline")
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "05_option_expression_model_inputs_task_test",
                "bundle": "05_option_expression_model_inputs",
                "params": {"underlying": "AAPL", "snapshot_time": "2026-04-24T09:30:02.500000-04:00"},
                "output_root": str(Path(tmp) / "task"),
            }
            writer = FakeSqlWriter()
            result = module.run(task_key, run_id="run", client=FakeThetaDataClient(), sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["option_expression_option_chain_snapshot"], 1)
            self.assertEqual(result.row_counts["option_chain_snapshot_contracts"], 1)
            call = writer.calls[0]
            self.assertEqual(call["table"], "option_expression_option_chain_snapshot")
            self.assertEqual(call["key_columns"], ["run_id", "underlying", "snapshot_time"])
            row = call["rows"][0]
            self.assertEqual(row["underlying"], "AAPL")
            self.assertEqual(row["snapshot_time"], "2026-04-24T09:30:02.500000-04:00")
            self.assertEqual(row["contract_count"], 1)
            self.assertEqual(row["contracts"][0]["option_right_type"], "CALL")
            self.assertNotIn("created_at", row)

    def test_model_input_bundles_emit_point_in_time_sql_manifest_rows(self):
        for bundle, required_roles in BUNDLES.items():
            with self.subTest(bundle=bundle), tempfile.TemporaryDirectory() as tmp:
                module = import_module(f"trading_data.data_bundles.{bundle}.pipeline")
                input_paths = {role: str(Path(tmp) / f"{role}.csv") for role in required_roles}
                for path in input_paths.values():
                    Path(path).write_text("placeholder\n", encoding="utf-8")
                task_key = {
                    "task_id": f"{bundle}_task_test",
                    "bundle": bundle,
                    "params": {"as_of": "2026-04-28T09:30:00-04:00", "input_paths": input_paths},
                    "output_root": str(Path(tmp) / "task"),
                }
                writer = FakeSqlWriter()
                result = module.run(task_key, run_id="run", sql_writer=writer)
                self.assertEqual(result.status, "succeeded")
                self.assertGreaterEqual(result.row_counts["model_input_artifact_reference"], len(required_roles))
                self.assertFalse((Path(task_key["output_root"]) / "runs" / "run" / "saved" / f"{bundle}.csv").exists())
                self.assertEqual(len(writer.calls), 1)
                call = writer.calls[0]
                self.assertEqual(call["table"], "model_input_artifact_reference")
                self.assertEqual(call["key_columns"], ["run_id", "bundle", "input_role", "data_kind", "artifact_reference"])
                rows = call["rows"]
                self.assertTrue(rows)
                self.assertEqual({row["bundle"] for row in rows}, {bundle})
                self.assertEqual({row["as_of"] for row in rows}, {"2026-04-28T09:30:00-04:00"})
                receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text(encoding="utf-8"))
                self.assertEqual(receipt["runs"][0]["status"], "succeeded")

    def test_market_regime_missing_time_range_fails_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = import_module("trading_data.data_bundles.01_market_regime_model_inputs.pipeline")
            task_key = {
                "task_id": "01_market_regime_model_inputs_task_bad",
                "bundle": "01_market_regime_model_inputs",
                "params": {"end": "2026-04-25"},
                "output_root": str(Path(tmp) / "task"),
            }
            result = module.run(task_key, run_id="run")
            self.assertEqual(result.status, "failed")
            self.assertIn("params.start is required", result.details["error"]["message"])


if __name__ == "__main__":
    unittest.main()
