import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path

from feed_availability.http import HttpResult

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
        return {"storage_target_id": "test_postgres", "driver": "postgresql", "schema": "trading_source", "table": table, "qualified_table": f"{table}", "rows_written": len(rows)}


class Secret:
    alias = "alpaca"
    path = Path("/root/secrets/alpaca.json")
    present = True
    keys_present = ("api_key", "secret_key")
    values = {"api_key": "k", "secret_key": "s", "data_endpoint": "https://data.alpaca.markets"}


class NumberedDataSourceTests(unittest.TestCase):
    def test_market_regime_source_fetches_universe_bars_as_one_sql_long_table(self):
        module = import_module("data_sources.source_01_market_regime.pipeline")
        old_load_secret = module.load_secret_alias
        module.load_secret_alias = lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                universe_path = Path(tmp) / "market_regime_etf_universe.csv"
                universe_path.write_text(
                    "symbol,universe_type,exposure_type,bar_grain,fund_name,issuer_name\n"
                    "SPY,broad_market,core,1d,SPDR S&P 500 ETF,State Street\n"
                    "BITW,sector_observation_etf,crypto_beta,30m,Bitwise 10 Crypto Index ETF,Bitwise\n",
                    encoding="utf-8",
                )
                task_key = {
                    "task_id": "source_01_market_regime_task_test",
                    "source": "source_01_market_regime",
                    "params": {"start": "2026-04-24", "end": "2026-04-25", "market_regime_etf_universe_path": str(universe_path), "max_pages": 2},
                    "output_root": str(Path(tmp) / "task"),
                }
                writer = FakeSqlWriter()
                result = module.run(task_key, run_id="run", client=FakeBarsClient(), sql_writer=writer)
                self.assertEqual(result.status, "succeeded")
                self.assertEqual(result.row_counts["source_01_market_regime"], 2)
                self.assertFalse((Path(task_key["output_root"]) / "runs" / "run" / "saved" / "source_01_market_regime.csv").exists())
                self.assertEqual(result.references, [str(Path(task_key["output_root"]) / "completion_receipt.json"), "source_01_market_regime"])
                self.assertEqual(len(writer.calls), 1)
                call = writer.calls[0]
                self.assertEqual(call["table"], "source_01_market_regime")
                self.assertEqual(call["key_columns"], ["symbol", "timeframe", "timestamp"])
                rows = sorted(call["rows"], key=lambda row: row["symbol"])
                self.assertEqual(len(rows), 2)
                self.assertEqual({row["symbol"]: row["timeframe"] for row in rows}, {"BITW": "30Min", "SPY": "1Day"})
                self.assertNotIn("run_id", rows[0])
                self.assertNotIn("task_id", rows[0])
                self.assertEqual(call["columns"], ["symbol", "timeframe", "timestamp", "bar_open", "bar_high", "bar_low", "bar_close", "bar_volume", "bar_vwap", "bar_trade_count"])
        finally:
            module.load_secret_alias = old_load_secret

    def test_strategy_selection_source_writes_bar_liquidity_sql_rows(self):
        module = import_module("data_sources.source_03_strategy_selection.pipeline")
        old_load_secret = module.load_secret_alias
        module.load_secret_alias = lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                task_key = {
                    "task_id": "source_03_strategy_selection_task_test",
                    "source": "source_03_strategy_selection",
                    "params": {"start": "2026-04-24T13:30:00Z", "end": "2026-04-24T13:31:00Z", "symbols": ["NVDA"]},
                    "output_root": str(Path(tmp) / "task"),
                }
                writer = FakeSqlWriter()
                result = module.run(task_key, run_id="run", client=FakeStrategySelectionClient(), sql_writer=writer)
                self.assertEqual(result.status, "succeeded")
                self.assertEqual(result.row_counts["source_03_strategy_selection"], 1)
                call = writer.calls[0]
                self.assertEqual(call["table"], "source_03_strategy_selection")
                self.assertEqual(call["key_columns"], ["symbol", "timeframe", "timestamp"])
                row = call["rows"][0]
                self.assertEqual(row["symbol"], "NVDA")
                self.assertEqual(row["timeframe"], "1Min")
                self.assertEqual(row["timestamp"], "2026-04-24T09:30:00-04:00")
                self.assertEqual(row["dollar_volume"], 100500.0)
                self.assertAlmostEqual(row["avg_spread"], 0.2)
                self.assertAlmostEqual(row["spread_bps"], 19.890601690701146)
                self.assertNotIn("run_id", row)
                self.assertNotIn("task_id", row)
                self.assertNotIn("created_at", row)
        finally:
            module.load_secret_alias = old_load_secret

    def test_option_expression_source_writes_option_snapshot_sql_row(self):
        module = import_module("data_sources.source_05_option_expression.pipeline")
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "source_05_option_expression_task_test",
                "source": "source_05_option_expression",
                "params": {"underlying": "AAPL", "snapshot_time": "2026-04-24T09:30:02.500000-04:00"},
                "output_root": str(Path(tmp) / "task"),
            }
            writer = FakeSqlWriter()
            result = module.run(task_key, run_id="run", client=FakeThetaDataClient(), sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["source_05_option_expression"], 1)
            self.assertEqual(result.row_counts["option_chain_snapshot_contracts"], 1)
            call = writer.calls[0]
            self.assertEqual(call["table"], "source_05_option_expression")
            self.assertEqual(call["key_columns"], ["underlying", "snapshot_time", "snapshot_type", "option_symbol"])
            row = call["rows"][0]
            self.assertEqual(row["underlying"], "AAPL")
            self.assertEqual(row["snapshot_time"], "2026-04-24T09:30:02.500000-04:00")
            self.assertEqual(row["snapshot_type"], "entry")
            self.assertEqual(row["option_right_type"], "CALL")
            self.assertEqual(row["bid"], 1.15)
            self.assertEqual(row["implied_vol"], 0.64)
            self.assertEqual(row["delta"], 0.52)
            self.assertNotIn("quote_timestamp", row)
            self.assertNotIn("iv_timestamp", row)
            self.assertNotIn("greeks_timestamp", row)
            self.assertNotIn("quote_timestamp", call["columns"])
            self.assertNotIn("iv_timestamp", call["columns"])
            self.assertNotIn("greeks_timestamp", call["columns"])
            self.assertNotIn("contracts", row)
            self.assertNotIn("run_id", row)
            self.assertNotIn("task_id", row)
            self.assertNotIn("created_at", row)

    def test_position_execution_source_writes_selected_contract_timeseries(self):
        module = import_module("data_sources.source_06_position_execution.pipeline")
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "source_06_position_execution_task_test",
                "source": "source_06_position_execution",
                "params": {
                    "selected_contracts": [
                        {
                            "underlying": "AAPL",
                            "option_symbol": "AAPL260515C270",
                            "expiration": "2026-05-15",
                            "option_right_type": "CALL",
                            "strike": 270,
                            "entry_time": "2026-04-24T09:30:00-04:00",
                            "exit_time": "2026-04-24T09:31:00-04:00",
                            "timeframe": "1Min",
                            "option_rows": [
                                {"timestamp": "2026-04-24T09:30:00-04:00", "bar_open": 1.1, "bar_high": 1.3, "bar_low": 1.0, "bar_close": 1.2, "bar_volume": 10, "bar_trade_count": 2, "bar_vwap": 1.18},
                                {"timestamp": "2026-04-24T10:31:00-04:00", "bar_open": 1.4, "bar_high": 1.5, "bar_low": 1.3, "bar_close": 1.35, "bar_volume": 8, "bar_trade_count": 1, "bar_vwap": 1.38},
                                {"timestamp": "2026-04-24T10:32:00-04:00", "bar_open": 1.6, "bar_high": 1.7, "bar_low": 1.5, "bar_close": 1.65, "bar_volume": 3, "bar_trade_count": 1, "bar_vwap": 1.62},
                            ],
                        }
                    ]
                },
                "output_root": str(Path(tmp) / "task"),
            }
            writer = FakeSqlWriter()
            result = module.run(task_key, run_id="run", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["source_06_position_execution"], 2)
            call = writer.calls[0]
            self.assertEqual(call["table"], "source_06_position_execution")
            self.assertEqual(call["key_columns"], ["option_symbol", "timeframe", "timestamp"])
            self.assertNotIn("run_id", call["columns"])
            rows = call["rows"]
            self.assertEqual({row["option_symbol"] for row in rows}, {"AAPL260515C270"})
            self.assertEqual(rows[-1]["timestamp"], "2026-04-24T10:31:00-04:00")

    def test_event_overlay_source_writes_one_row_per_event(self):
        module = import_module("data_sources.source_07_event_overlay.pipeline")
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "source_07_event_overlay_task_test",
                "source": "source_07_event_overlay",
                "params": {
                    "start": "2026-04-24T09:30:00-04:00",
                    "end": "2026-04-24T16:00:00-04:00",
                    "focus_sectors": ["semiconductor"],
                    "symbols": ["NVDA"],
                    "events": [
                        {
                            "event_id": "evt_nvda_abnormal_1",
                            "event_time": "2026-04-24T09:35:00-04:00",
                            "available_time": "2026-04-24T09:36:00-04:00",
                            "information_role_type": "prior_signal",
                            "event_category_type": "equity_abnormal_activity",
                            "scope_type": "symbol",
                            "symbol": "NVDA",
                            "title": "NVDA abnormal opening activity",
                            "summary": "NVDA opened with abnormal return and volume.",
                            "source_name": "alpaca_equity_market_data",
                            "reference_type": "internal_artifact_path",
                            "reference": "/tmp/equity_abnormal_activity_event.csv",
                        },
                        {
                            "event_id": "evt_macro_1",
                            "event_time": "2026-04-24T08:30:00-04:00",
                            "information_role_type": "lagging_evidence",
                            "event_category_type": "macro_data",
                            "scope_type": "macro",
                            "title": "US durable goods release",
                            "summary": "Macro calendar release overview.",
                            "source_name": "07_feed_trading_economics_calendar_web",
                            "reference_type": "web_url",
                            "reference": "https://tradingeconomics.com/united-states/calendar",
                        },
                    ],
                },
                "output_root": str(Path(tmp) / "task"),
            }
            writer = FakeSqlWriter()
            result = module.run(task_key, run_id="run", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["source_07_event_overlay"], 2)
            call = writer.calls[0]
            self.assertEqual(call["table"], "source_07_event_overlay")
            self.assertEqual(call["key_columns"], ["event_id"])
            self.assertNotIn("run_id", call["columns"])
            self.assertEqual({row["information_role_type"] for row in call["rows"]}, {"lagging_evidence", "prior_signal"})

    def test_market_regime_missing_time_range_fails_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = import_module("data_sources.source_01_market_regime.pipeline")
            task_key = {
                "task_id": "source_01_market_regime_task_bad",
                "source": "source_01_market_regime",
                "params": {"end": "2026-04-25"},
                "output_root": str(Path(tmp) / "task"),
            }
            result = module.run(task_key, run_id="run")
            self.assertEqual(result.status, "failed")
            self.assertIn("params.start is required", result.details["error"]["message"])


if __name__ == "__main__":
    unittest.main()
