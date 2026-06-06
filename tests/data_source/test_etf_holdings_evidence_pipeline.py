import csv
import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path


class FakeSqlWriter:
    def __init__(self):
        self.calls = []

    def write_rows(self, *, table, columns, rows, key_columns):
        self.calls.append({"table": table, "columns": list(columns), "rows": list(rows), "key_columns": list(key_columns)})
        return {"storage_target_id": "test_postgres", "driver": "postgresql", "schema": "trading_data", "table": table, "qualified_table": f"{table}", "rows_written": len(rows)}


class EtfHoldingsEvidencePipelineTests(unittest.TestCase):
    def test_holdings_window_is_half_open(self):
        module = import_module("data_source.m02_sector_context_data_acquisition.pipeline")
        task_key = {"task_id": "m02_window", "source": "m02_sector_context_data_acquisition", "params": {"start": "2026-04-24", "end": "2026-04-25"}, "output_root": "/tmp/m02_window"}
        context = module.build_context(task_key, "run")
        universe = [{"symbol": "XLK", "issuer_name": "State Street / SPDR", "universe_type": "sector_observation_etf", "exposure_type": "sp500_sector"}]
        payload = module.SourcePayload(
            universe_rows=universe,
            selected_symbols=("XLK",),
            raw_rows=[
                {"etf_symbol": "XLK", "holding_symbol": "NVDA", "holding_name": "NVIDIA Corp", "asset_class": "Equity", "as_of_date": "2026-04-24"},
                {"etf_symbol": "XLK", "holding_symbol": "AMD", "holding_name": "Advanced Micro Devices", "asset_class": "Equity", "as_of_date": "2026-04-25"},
            ],
        )
        result, cleaned = module.clean(context, payload)
        self.assertEqual(result.row_counts["m02_sector_context_data_acquisition"], 1)
        self.assertEqual(result.details["skipped"]["outside_window"], 1)
        self.assertEqual(cleaned.rows[0]["holding_symbol"], "NVDA")

    def test_holdings_window_normalizes_us_date_format(self):
        module = import_module("data_source.m02_sector_context_data_acquisition.pipeline")
        task_key = {"task_id": "m02_us_date", "source": "m02_sector_context_data_acquisition", "params": {"start": "2026-05-18", "end": "2026-05-19"}, "output_root": "/tmp/m02_us_date"}
        context = module.build_context(task_key, "run")
        payload = module.SourcePayload(
            universe_rows=[{"symbol": "XLV", "issuer_name": "State Street / SPDR", "universe_type": "sector_observation_etf", "exposure_type": "sp500_sector"}],
            selected_symbols=("XLV",),
            raw_rows=[{"etf_symbol": "XLV", "holding_symbol": "UNH", "holding_name": "UnitedHealth Group", "asset_class": "Equity", "as_of_date": "05/18/2026"}],
        )

        result, cleaned = module.clean(context, payload)

        self.assertEqual(result.row_counts["m02_sector_context_data_acquisition"], 1)
        self.assertEqual(cleaned.rows[0]["as_of_date"], "2026-05-18")

    def test_available_time_defaults_to_next_regular_us_equity_open(self):
        module = import_module("data_source.m02_sector_context_data_acquisition.pipeline")
        row = {"available_time": "", "as_of_date": "2026-04-24"}
        self.assertEqual(module._available_time({}, row, "2026-04-24"), "2026-04-27T09:30:00-04:00")

    def test_etf_holdings_evidence_source_writes_filtered_us_equity_holdings(self):
        with tempfile.TemporaryDirectory() as tmp:
            universe = Path(tmp) / "layer_01_02_market_context_etf_universe.csv"
            universe.write_text(
                "symbol,universe_type,model_layer,exposure_type,feature_grain,fund_name,issuer_name\n"
                "SPY,market_state_etf,layer_01_market_regime,us_equity_core,1d,SPDR S&P 500 ETF,State Street\n"
                "XLK,sector_observation_etf,layer_02_sector_context,sp500_sector,1d,Technology Select Sector SPDR Fund,State Street / SPDR\n",
                encoding="utf-8",
            )
            holdings = Path(tmp) / "xlk_holdings.csv"
            with holdings.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Ticker", "Name", "Weight", "Shares", "Market Value", "Asset Class", "Sector"])
                writer.writeheader()
                writer.writerows([
                    {"Ticker": "NVDA", "Name": "NVIDIA Corp", "Weight": "20", "Shares": "100", "Market Value": "1000", "Asset Class": "Equity", "Sector": "Information Technology"},
                    {"Ticker": "CASH", "Name": "Cash Collateral", "Weight": "2", "Asset Class": "Cash", "Sector": "Cash"},
                    {"Ticker": "SAP", "Name": "SAP SE", "Weight": "1", "Asset Class": "Equity", "Sector": "Technology"},
                ])
            task_key = {
                "task_id": "m02_sector_context_data_acquisition_task_test",
                "source": "m02_sector_context_data_acquisition",
                "params": {
                    "start": "2026-04-24",
                    "end": "2026-04-25",
                    "market_regime_etf_universe_path": str(universe),
                    "available_time": "2026-04-25T09:30:00-04:00",
                    "holding_feed_payloads": {"XLK": {"csv_path": str(holdings), "as_of_date": "2026-04-24"}},
                },
                "output_root": str(Path(tmp) / "task"),
            }
            module = import_module("data_source.m02_sector_context_data_acquisition.pipeline")
            sql_writer = FakeSqlWriter()
            result = module.run(task_key, run_id="run", sql_writer=sql_writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["m02_sector_context_data_acquisition"], 1)
            manifest = json.loads((Path(task_key["output_root"]) / "runs" / "run" / "request_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["model_layer_filter"], "layer_02_sector_context")
            self.assertEqual(manifest["universe_type_filter"], "sector_observation_etf")
            self.assertEqual(manifest["symbols"], ["XLK"])
            self.assertEqual(len(sql_writer.calls), 1)
            call = sql_writer.calls[0]
            self.assertEqual(call["table"], "m02_sector_context_data_acquisition")
            self.assertEqual(call["key_columns"], ["etf_symbol", "as_of_date", "holding_symbol"])
            self.assertEqual(call["columns"], ["etf_symbol", "issuer_name", "universe_type", "exposure_type", "as_of_date", "available_time", "holding_symbol", "holding_name", "weight", "shares", "market_value", "sector_type"])
            rows = call["rows"]
            self.assertEqual(rows[0]["holding_symbol"], "NVDA")
            self.assertEqual(rows[0]["etf_symbol"], "XLK")
            self.assertEqual(rows[0]["universe_type"], "sector_observation_etf")
            self.assertEqual(rows[0]["exposure_type"], "sp500_sector")
            self.assertEqual(rows[0]["available_time"], "2026-04-25T09:30:00-04:00")
            self.assertNotIn("run_id", rows[0])
            self.assertNotIn("task_id", rows[0])
            self.assertNotIn("created_at", rows[0])
            self.assertNotIn("cusip", rows[0])
            self.assertNotIn("sedol", rows[0])
            self.assertNotIn("asset_class", rows[0])
            self.assertNotIn("source_url", rows[0])
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["runs"][0]["status"], "succeeded")

    def test_missing_payload_can_use_feed_default_source_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            universe = Path(tmp) / "layer_01_02_market_context_etf_universe.csv"
            universe.write_text(
                "symbol,universe_type,model_layer,exposure_type,feature_grain,fund_name,issuer_name\n"
                "XLK,sector_observation_etf,layer_02_sector_context,sp500_sector,1d,Technology Select Sector SPDR Fund,State Street / SPDR\n",
                encoding="utf-8",
            )
            task_key = {
                "task_id": "m02_etf_holdings_default_feed_test",
                "source": "m02_sector_context_data_acquisition",
                "params": {
                    "start": "2026-04-24",
                    "end": "2026-04-25",
                    "market_regime_etf_universe_path": str(universe),
                    "symbols": ["XLK"],
                    "holding_feed_payloads": {},
                },
                "manager_controls": {
                    "allow_live_provider_calls": True,
                    "autonomous_historical_provider_acquisition": True,
                    "allowed_providers": ["etf_issuer_holdings"],
                    "allowed_endpoint_families": ["holdings_file"],
                    "max_requests": 50,
                    "max_symbols": 25,
                    "max_time_window": "31d",
                },
                "output_root": str(Path(tmp) / "task"),
            }
            module = import_module("data_source.m02_sector_context_data_acquisition.pipeline")
            captured = {}

            def fake_fetch(context):
                captured["params"] = context.task_key["params"]
                captured["manager_controls"] = context.task_key["manager_controls"]
                return module.StepResult("succeeded", [], {"feed_payloads": 1}), object()

            def fake_clean(context, payload):
                return module.StepResult("succeeded", [], {"etf_holding_snapshot": 1}), type("Payload", (), {"rows": [{"etf_symbol": "XLK", "holding_symbol": "MSFT", "holding_name": "Microsoft Corp", "asset_class": "Equity", "as_of_date": "2026-04-24"}]})()

            original_fetch = module.fetch_holding_feed
            original_clean = module.clean_holding_feed
            module.fetch_holding_feed = fake_fetch
            module.clean_holding_feed = fake_clean
            try:
                writer = FakeSqlWriter()
                result = module.run(task_key, run_id="run", sql_writer=writer)
            finally:
                module.fetch_holding_feed = original_fetch
                module.clean_holding_feed = original_clean

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(captured["params"]["etf_symbol"], "XLK")
            self.assertEqual(captured["params"]["issuer_name"], "State Street / SPDR")
            self.assertTrue(captured["manager_controls"]["allow_live_provider_calls"])
            self.assertEqual(writer.calls[0]["rows"][0]["holding_symbol"], "MSFT")

    def test_missing_window_holdings_are_reported_as_partial_coverage_not_failure(self):
        module = import_module("data_source.m02_sector_context_data_acquisition.pipeline")
        task_key = {"task_id": "m02_missing_window", "source": "m02_sector_context_data_acquisition", "params": {"start": "2026-05-18", "end": "2026-05-19"}, "output_root": "/tmp/m02_missing_window"}
        context = module.build_context(task_key, "run")
        payload = module.SourcePayload(
            universe_rows=[
                {"symbol": "XLF", "issuer_name": "State Street / SPDR", "universe_type": "sector_observation_etf", "exposure_type": "sp500_sector"},
            ],
            selected_symbols=("XLF",),
            raw_rows=[
                {"etf_symbol": "XLF", "holding_symbol": "JPM", "holding_name": "JPMorgan Chase & Co", "asset_class": "Equity", "as_of_date": "2026-01-02"},
            ],
        )

        result, cleaned = module.clean(context, payload)

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.row_counts["m02_sector_context_data_acquisition"], 0)
        self.assertEqual(cleaned.rows, [])
        self.assertEqual(result.details["missing_symbols"], ["XLF"])
        self.assertIn("accepted_partial_coverage", result.details["missing_symbol_policy"])
        self.assertEqual(result.details["symbol_coverage"]["XLF"]["outside_window"], 1)

    def test_missing_as_of_date_holdings_are_not_backfilled_from_request_window(self):
        module = import_module("data_source.m02_sector_context_data_acquisition.pipeline")
        task_key = {"task_id": "m02_missing_as_of", "source": "m02_sector_context_data_acquisition", "params": {"start": "2016-01-01", "end": "2016-02-01"}, "output_root": "/tmp/m02_missing_as_of"}
        context = module.build_context(task_key, "run")
        payload = module.SourcePayload(
            universe_rows=[
                {"symbol": "XLU", "issuer_name": "State Street / SPDR", "universe_type": "sector_observation_etf", "exposure_type": "sp500_sector"},
            ],
            selected_symbols=("XLU",),
            raw_rows=[
                {"etf_symbol": "XLU", "holding_symbol": "NEE", "holding_name": "NextEra Energy Inc", "asset_class": "Equity", "as_of_date": ""},
            ],
        )

        result, cleaned = module.clean(context, payload)

        self.assertEqual(cleaned.rows, [])
        self.assertEqual(result.details["skipped"]["missing_as_of_date"], 1)
        self.assertEqual(result.details["symbol_coverage"]["XLU"]["missing_as_of_date"], 1)
        self.assertEqual(result.details["missing_symbols"], ["XLU"])


if __name__ == "__main__":
    unittest.main()
