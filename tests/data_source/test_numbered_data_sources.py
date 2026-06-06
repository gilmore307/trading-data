import json
import contextlib
import io
import tempfile
import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

from feed_availability.http import HttpResult

class FakeBarsClient:
    def get(self, url, *, params=None, headers=None):
        symbol = url.rstrip("/").split("/")[-2]
        timeframe = (params or {}).get("timeframe", "1Day")
        payload = {"bars": [{"t": "2026-04-24T13:30:00Z", "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 1000, "vw": 100.25, "n": 10}]}
        if timeframe != "1Min":
            payload["bars"][0]["t"] = "2026-04-24T14:00:00Z"
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
        return {"storage_target_id": "test_postgres", "driver": "postgresql", "schema": "trading_data", "table": table, "qualified_table": f"{table}", "rows_written": len(rows)}


class FakeSqlReader:
    def __init__(self, rows_by_table=None):
        self.rows_by_table = rows_by_table or {}
        self.calls = []

    def read_rows(self, **kwargs):
        self.calls.append(kwargs)
        rows = self.rows_by_table.get(kwargs["table"], [])
        where_equals = kwargs.get("where_equals") or {}
        return [dict(row) for row in rows if all(row.get(column) == value for column, value in where_equals.items())]


class Secret:
    alias = "alpaca"
    path = Path("/root/secrets/alpaca.json")
    present = True
    keys_present = ("api_key", "secret_key")
    values = {"api_key": "k", "secret_key": "s", "data_endpoint": "https://data.alpaca.markets"}


class NumberedDataSourceTests(unittest.TestCase):
    def test_market_regime_source_fetches_universe_bars_as_one_sql_long_table(self):
        module = import_module("data_source.m01_market_regime_data_acquisition.pipeline")
        old_load_secret = module.load_secret_alias
        module.load_secret_alias = lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                universe_path = Path(tmp) / "layer_01_02_market_context_etf_universe.csv"
                universe_path.write_text(
                    "symbol,universe_type,exposure_type,feature_grain,fund_name,issuer_name\n"
                    "SPY,broad_market,core,1d,SPDR S&P 500 ETF,State Street\n"
                    "BITW,sector_observation_etf,crypto_beta,30m,Bitwise 10 Crypto Index ETF,Bitwise\n",
                    encoding="utf-8",
                )
                task_key = {
                    "task_id": "m01_market_regime_data_acquisition_task_test",
                    "source": "m01_market_regime_data_acquisition",
                    "params": {"start": "2026-04-24", "end": "2026-04-25", "market_regime_etf_universe_path": str(universe_path), "max_pages": 2},
                    "output_root": str(Path(tmp) / "task"),
                }
                writer = FakeSqlWriter()
                result = module.run(task_key, run_id="run", client=FakeBarsClient(), sql_writer=writer, client_is_fixture=True)
                self.assertEqual(result.status, "succeeded")
                self.assertEqual(result.row_counts["m01_market_regime_data_acquisition"], 2)
                self.assertFalse((Path(task_key["output_root"]) / "runs" / "run" / "saved" / "m01_market_regime_data_acquisition.csv").exists())
                self.assertEqual(result.references, [str(Path(task_key["output_root"]) / "completion_receipt.json"), "m01_market_regime_data_acquisition"])
                self.assertEqual(len(writer.calls), 1)
                call = writer.calls[0]
                self.assertEqual(call["table"], "m01_market_regime_data_acquisition")
                self.assertEqual(call["key_columns"], ["symbol", "timeframe", "timestamp"])
                rows = sorted(call["rows"], key=lambda row: row["symbol"])
                self.assertEqual(len(rows), 2)
                self.assertEqual({row["symbol"]: row["timeframe"] for row in rows}, {"BITW": "1Min", "SPY": "1Min"})
                self.assertNotIn("run_id", rows[0])
                self.assertNotIn("task_id", rows[0])
                self.assertEqual(call["columns"], ["symbol", "timeframe", "timestamp", "bar_open", "bar_high", "bar_low", "bar_close", "bar_volume", "bar_vwap", "bar_trade_count"])
        finally:
            module.load_secret_alias = old_load_secret

    def test_market_regime_source_rejects_non_one_minute_download_timeframe(self):
        module = import_module("data_source.m01_market_regime_data_acquisition.pipeline")
        old_load_secret = module.load_secret_alias
        module.load_secret_alias = lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                universe_path = Path(tmp) / "layer_01_02_market_context_etf_universe.csv"
                universe_path.write_text(
                    "symbol,universe_type,exposure_type,feature_grain,fund_name,issuer_name\n"
                    "SPY,broad_market,core,1d,SPDR S&P 500 ETF,State Street\n",
                    encoding="utf-8",
                )
                task_key = {
                    "task_id": "m01_market_regime_data_acquisition_task_bad_timeframe",
                    "source": "m01_market_regime_data_acquisition",
                    "params": {"start": "2026-04-24", "end": "2026-04-25", "timeframe": "1Day", "market_regime_etf_universe_path": str(universe_path)},
                    "output_root": str(Path(tmp) / "task"),
                }
                result = module.run(task_key, run_id="run", client=FakeBarsClient(), sql_writer=FakeSqlWriter(), client_is_fixture=True)

            self.assertEqual(result.status, "failed")
        finally:
            module.load_secret_alias = old_load_secret

    def test_option_expression_source_writes_option_snapshot_sql_row(self):
        module = import_module("data_source.m09_option_expression_data_acquisition.pipeline")
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "m09_option_expression_data_acquisition_task_test",
                "source": "m09_option_expression_data_acquisition",
                "params": {"underlying": "AAPL", "snapshot_time": "2026-04-24T09:30:02.500000-04:00", "historical_mode": False},
                "output_root": str(Path(tmp) / "task"),
            }
            writer = FakeSqlWriter()
            result = module.run(task_key, run_id="run", client=FakeThetaDataClient(), sql_writer=writer, client_is_fixture=True)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["m09_option_expression_data_acquisition"], 1)
            self.assertEqual(result.row_counts["option_chain_state_source"], 1)
            self.assertEqual(result.row_counts["option_chain_snapshot_contracts"], 1)
            self.assertEqual([call["table"] for call in writer.calls], ["option_chain_state_source", "m09_option_expression_data_acquisition"])
            shared_call = writer.calls[0]
            self.assertEqual(shared_call["key_columns"], ["underlying", "snapshot_time", "option_symbol"])
            self.assertEqual(shared_call["rows"][0]["underlying"], "AAPL")
            self.assertEqual(shared_call["rows"][0]["option_symbol"], "AAPL_2026-05-15_C_270")
            call = writer.calls[1]
            self.assertEqual(call["table"], "m09_option_expression_data_acquisition")
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
            manifest = json.loads((Path(task_key["output_root"]) / "runs" / "run" / "request_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["params"]["max_dte"], 45)
            self.assertEqual(manifest["params"]["strike_range"], 5)
            self.assertEqual(manifest["params"]["option_bucket_policy_ref"], "LAYER_09_OPTION_BUCKET_STRIKE_POLICY")
            self.assertNotIn("created_at", row)

    def test_option_expression_source_reuses_shared_option_chain_rows_before_provider_fetch(self):
        module = import_module("data_source.m09_option_expression_data_acquisition.pipeline")
        snapshot_time = "2026-04-24T09:30:02.500000-04:00"
        shared_row = {
            "underlying": "AAPL",
            "snapshot_time": snapshot_time,
            "option_symbol": "AAPL_2026-05-15_C_270",
            "expiration": "2026-05-15",
            "option_right_type": "CALL",
            "strike": 270.0,
            "bid": 1.15,
            "ask": 1.25,
            "mid": 1.2,
            "spread": 0.1,
            "spread_pct": 0.0833,
            "bid_size": 10,
            "ask_size": 12,
            "bid_exchange": None,
            "ask_exchange": None,
            "bid_condition": None,
            "ask_condition": None,
            "implied_vol": 0.64,
            "iv_error": None,
            "delta": 0.52,
            "theta": -0.03,
            "vega": 0.14,
            "rho": 0.01,
            "epsilon": None,
            "lambda": None,
            "underlying_price": 248.9,
            "underlying_timestamp": snapshot_time,
            "days_to_expiration": 21,
            "bar_open": None,
            "bar_high": None,
            "bar_low": None,
            "bar_close": None,
            "bar_volume": None,
            "bar_trade_count": None,
            "bar_vwap": None,
            "trade_notional": None,
            "open_interest": None,
            "open_interest_change": None,
            "source_run_ref": "option_chain_state_source/run_001",
        }
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "m09_option_expression_data_acquisition_task_test",
                "source": "m09_option_expression_data_acquisition",
                "params": {"underlying": "AAPL", "snapshot_time": snapshot_time},
                "output_root": str(Path(tmp) / "task"),
            }
            writer = FakeSqlWriter()
            reader = FakeSqlReader({"option_chain_state_source": [shared_row]})
            result = module.run(task_key, run_id="run", sql_reader=reader, sql_writer=writer)

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(len(reader.calls), 1)
        self.assertEqual(reader.calls[0]["table"], "option_chain_state_source")
        self.assertEqual(result.row_counts["m09_option_expression_data_acquisition"], 1)
        self.assertEqual(result.row_counts["option_chain_state_source"], 1)
        self.assertEqual([call["table"] for call in writer.calls], ["option_chain_state_source", "m09_option_expression_data_acquisition"])
        self.assertEqual(writer.calls[1]["rows"][0]["option_symbol"], "AAPL_2026-05-15_C_270")

    def test_option_expression_cli_accepts_task_key_manifest_batch(self):
        module = import_module("data_source.m09_option_expression_data_acquisition.__main__")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_key_paths = []
            for index in range(2):
                path = root / f"task_{index}.json"
                path.write_text(
                    json.dumps(
                        {
                            "task_id": f"m09_option_expression_data_acquisition_task_{index}",
                            "source": "m09_option_expression_data_acquisition",
                            "params": {"underlying": "AAPL", "snapshot_time": "2026-04-24T09:30:02.500000-04:00"},
                            "output_root": str(root / f"task_{index}"),
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                task_key_paths.append(str(path))
            manifest = root / "batch.json"
            manifest.write_text(json.dumps({"task_key_paths": task_key_paths}) + "\n", encoding="utf-8")
            captured = {}

            def fake_run_many(task_keys, **kwargs):
                captured["task_count"] = len(task_keys)
                captured["kwargs"] = kwargs
                return {
                    "contract_type": "m09_option_expression_data_acquisition_batch_result",
                    "batch_run_id": kwargs["batch_run_id"],
                    "task_count": len(task_keys),
                    "succeeded_count": len(task_keys),
                    "failed_count": 0,
                    "items": [{"task_id": task_key["task_id"], "status": "succeeded"} for task_key in task_keys],
                }

            with patch.object(module, "run_many", side_effect=fake_run_many):
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = module.main(["--task-key-manifest", str(manifest), "--batch-run-id", "batch_run"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["task_count"], 2)
        self.assertEqual(captured["kwargs"]["batch_run_id"], "batch_run")

    def test_selected_contract_tracking_source_writes_option_timeseries(self):
        module = import_module("data_source.m09_option_expression_data_acquisition_contract_path.pipeline")
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "m09_option_expression_data_acquisition_contract_path_task_test",
                "source": "m09_option_expression_data_acquisition_contract_path",
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
            self.assertEqual(result.row_counts["m09_option_expression_data_acquisition_contract_path"], 2)
            call = writer.calls[0]
            self.assertEqual(call["table"], "m09_option_expression_data_acquisition_contract_path")
            self.assertEqual(call["key_columns"], ["option_symbol", "timeframe", "timestamp"])
            self.assertNotIn("run_id", call["columns"])
            rows = call["rows"]
            self.assertEqual({row["option_symbol"] for row in rows}, {"AAPL260515C270"})
            self.assertEqual(rows[-1]["timestamp"], "2026-04-24T10:31:00-04:00")

    def test_event_overlay_source_writes_one_row_per_event(self):
        module = import_module("data_source.m10_event_risk_governor_data_acquisition.pipeline")
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "m10_event_risk_governor_data_acquisition_task_test",
                "source": "m10_event_risk_governor_data_acquisition",
                "params": {
                    "start": "2026-04-24T08:00:00-04:00",
                    "end": "2026-04-24T16:00:00-04:00",
                    "focus_sectors": ["semiconductor"],
                    "symbols": ["NVDA"],
                    "events": [
                        {
                            "event_id": "evt_nvda_10q_2026q1",
                            "event_time": "2026-04-24T09:35:00-04:00",
                            "available_time": "2026-04-24T09:36:00-04:00",
                            "information_role_type": "prior_signal",
                            "event_category_type": "sec_filing",
                            "scope_type": "symbol",
                            "symbol": "NVDA",
                            "title": "NVDA 10-Q filing",
                            "summary": "NVDA filed its quarterly report.",
                            "source_name": "sec_company_financials",
                            "reference_type": "sec_file_path",
                            "reference": "/tmp/sec/nvda-10q.html",
                            "source_artifact_path": "/tmp/sec/nvda-10q.html",
                        },
                        {
                            "event_id": "evt_nvda_news_covered_1",
                            "event_time": "2026-04-24T09:37:00-04:00",
                            "available_time": "2026-04-24T09:38:00-04:00",
                            "information_role_type": "lagging_evidence",
                            "event_category_type": "symbol_news",
                            "scope_type": "symbol",
                            "symbol": "NVDA",
                            "title": "News outlet reports NVDA filing",
                            "summary": "Article summarizes the same NVDA 10-Q filing.",
                            "source_name": "alpaca_equity_news",
                            "reference_type": "web_url",
                            "reference": "https://example.com/nvda-10q-news",
                            "canonical_event_id": "evt_nvda_10q_2026q1",
                            "dedup_status": "covered_by_canonical_event",
                            "source_priority": "derivative_news",
                            "coverage_reason": "agent_read_article_found_no_new_information_beyond_sec_filing",
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
                            "reference_type": "source_reference",
                            "reference": "trading_economics_calendar_event.csv",
                        },
                        {
                            "event_id": "evt_nvda_false_breakout_1",
                            "event_time": "2026-04-24T10:15:00-04:00",
                            "available_time": "2026-04-24T10:16:00-04:00",
                            "information_role_type": "prior_signal",
                            "event_category_type": "price_action",
                            "scope_type": "symbol",
                            "symbol": "NVDA",
                            "title": "NVDA false breakout detector event",
                            "summary": "Price-action detector flagged false_breakout;liquidity_sweep_high.",
                            "source_name": "m10_event_risk_governor_data_acquisition.equity_abnormal_activity",
                            "reference_type": "internal_artifact_path",
                            "reference": "storage/events/nvda_false_breakout.json",
                        },
                    ],
                },
                "output_root": str(Path(tmp) / "task"),
            }
            writer = FakeSqlWriter()
            result = module.run(task_key, run_id="run", sql_writer=writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["m10_event_risk_governor_data_acquisition"], 4)
            call = writer.calls[0]
            self.assertEqual(call["table"], "m10_event_risk_governor_data_acquisition")
            self.assertEqual(call["key_columns"], ["event_id"])
            self.assertNotIn("run_id", call["columns"])
            self.assertIn("canonical_event_id", call["columns"])
            self.assertIn("dedup_status", call["columns"])
            self.assertIn("source_priority", call["columns"])
            self.assertIn("coverage_reason", call["columns"])
            self.assertIn("covered_by_event_id", call["columns"])
            self.assertIn("source_artifact_path", call["columns"])
            self.assertEqual({row["information_role_type"] for row in call["rows"]}, {"lagging_evidence", "prior_signal"})
            by_event = {row["event_id"]: row for row in call["rows"]}
            self.assertEqual(by_event["evt_nvda_10q_2026q1"]["canonical_event_id"], "evt_nvda_10q_2026q1")
            self.assertEqual(by_event["evt_nvda_10q_2026q1"]["source_artifact_path"], "/tmp/sec/nvda-10q.html")
            self.assertEqual(by_event["evt_nvda_10q_2026q1"]["dedup_status"], "canonical")
            self.assertEqual(by_event["evt_nvda_10q_2026q1"]["source_priority"], "official_disclosure")
            self.assertEqual(by_event["evt_nvda_news_covered_1"]["canonical_event_id"], "evt_nvda_10q_2026q1")
            self.assertEqual(by_event["evt_nvda_news_covered_1"]["covered_by_event_id"], "evt_nvda_10q_2026q1")
            self.assertEqual(by_event["evt_nvda_news_covered_1"]["dedup_status"], "covered_by_canonical_event")
            self.assertEqual(by_event["evt_nvda_news_covered_1"]["source_priority"], "derivative_news")
            self.assertEqual(by_event["evt_nvda_false_breakout_1"]["event_category_type"], "price_action")
            self.assertEqual(by_event["evt_nvda_false_breakout_1"]["source_priority"], "source_detector")

    def test_event_overlay_sql_ddl_includes_dedup_contract_fields(self):
        from storage.sql import _table_ddl

        ddl = _table_ddl("m10_event_risk_governor_data_acquisition", '"trading_data"."m10_event_risk_governor_data_acquisition"')
        self.assertIsNotNone(ddl)
        for column in {
            "canonical_event_id TEXT NOT NULL",
            "dedup_status TEXT NOT NULL",
            "source_priority TEXT NOT NULL",
            "coverage_reason TEXT",
            "covered_by_event_id TEXT",
            "source_artifact_path TEXT",
        }:
            self.assertIn(column, ddl)

    def test_option_chain_state_source_sql_ddl_is_typed_contract_table(self):
        from storage.sql import _table_ddl

        ddl = _table_ddl("option_chain_state_source", '"trading_data"."option_chain_state_source"')
        self.assertIsNotNone(ddl)
        self.assertIn("snapshot_time TIMESTAMPTZ NOT NULL", ddl)
        self.assertIn("strike DOUBLE PRECISION NOT NULL", ddl)
        self.assertIn("bar_volume DOUBLE PRECISION", ddl)
        self.assertIn("open_interest_change DOUBLE PRECISION", ddl)
        self.assertIn("PRIMARY KEY (underlying, snapshot_time, option_symbol)", ddl)

    def test_market_regime_missing_time_range_fails_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = import_module("data_source.m01_market_regime_data_acquisition.pipeline")
            task_key = {
                "task_id": "m01_market_regime_data_acquisition_task_bad",
                "source": "m01_market_regime_data_acquisition",
                "params": {"end": "2026-04-25"},
                "output_root": str(Path(tmp) / "task"),
            }
            result = module.run(task_key, run_id="run")
            self.assertEqual(result.status, "failed")
            self.assertIn("params.start is required", result.details["error"]["message"])


if __name__ == "__main__":
    unittest.main()
