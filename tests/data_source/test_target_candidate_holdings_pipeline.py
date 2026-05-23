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


class CandidateBuilderEtfHoldingsPipelineTests(unittest.TestCase):
    def test_holdings_window_is_half_open(self):
        module = import_module("data_source.source_02_target_candidate_holdings.pipeline")
        task_key = {"task_id": "source_02_window", "source": "source_02_target_candidate_holdings", "params": {"start": "2026-04-24", "end": "2026-04-25"}, "output_root": "/tmp/source_02_window"}
        context = module.build_context(task_key, "run")
        universe = [{"symbol": "SMH", "issuer_name": "VanEck", "universe_type": "sector_observation_etf", "exposure_type": "industry_chain"}]
        payload = module.SourcePayload(
            universe_rows=universe,
            selected_symbols=("SMH",),
            raw_rows=[
                {"etf_symbol": "SMH", "holding_symbol": "NVDA", "holding_name": "NVIDIA Corp", "asset_class": "Equity", "as_of_date": "2026-04-24"},
                {"etf_symbol": "SMH", "holding_symbol": "AMD", "holding_name": "Advanced Micro Devices", "asset_class": "Equity", "as_of_date": "2026-04-25"},
            ],
        )
        result, cleaned = module.clean(context, payload)
        self.assertEqual(result.row_counts["source_02_target_candidate_holdings"], 1)
        self.assertEqual(result.details["skipped"]["outside_window"], 1)
        self.assertEqual(cleaned.rows[0]["holding_symbol"], "NVDA")

    def test_holdings_window_normalizes_us_date_format(self):
        module = import_module("data_source.source_02_target_candidate_holdings.pipeline")
        task_key = {"task_id": "source_02_us_date", "source": "source_02_target_candidate_holdings", "params": {"start": "2026-05-18", "end": "2026-05-19"}, "output_root": "/tmp/source_02_us_date"}
        context = module.build_context(task_key, "run")
        payload = module.SourcePayload(
            universe_rows=[{"symbol": "ARKG", "issuer_name": "ARK Invest", "universe_type": "sector_observation_etf", "exposure_type": "thematic_growth"}],
            selected_symbols=("ARKG",),
            raw_rows=[{"etf_symbol": "ARKG", "holding_symbol": "TDOC", "holding_name": "Teladoc Health", "asset_class": "Equity", "as_of_date": "05/18/2026"}],
        )

        result, cleaned = module.clean(context, payload)

        self.assertEqual(result.row_counts["source_02_target_candidate_holdings"], 1)
        self.assertEqual(cleaned.rows[0]["as_of_date"], "2026-05-18")

    def test_available_time_defaults_to_next_regular_us_equity_open(self):
        module = import_module("data_source.source_02_target_candidate_holdings.pipeline")
        row = {"available_time": "", "as_of_date": "2026-04-24"}
        self.assertEqual(module._available_time({}, row, "2026-04-24"), "2026-04-27T09:30:00-04:00")

    def test_candidate_builder_holdings_source_writes_filtered_us_equity_holdings(self):
        with tempfile.TemporaryDirectory() as tmp:
            universe = Path(tmp) / "layer_01_02_market_context_etf_universe.csv"
            universe.write_text(
                "symbol,universe_type,model_layer,exposure_type,feature_grain,fund_name,issuer_name\n"
                "SPY,market_state_etf,layer_01_market_regime,us_equity_core,1d,SPDR S&P 500 ETF,State Street\n"
                "SMH,sector_observation_etf,layer_02_sector_context,industry_chain,1d,VanEck Semiconductor ETF,VanEck\n",
                encoding="utf-8",
            )
            holdings = Path(tmp) / "smh_holdings.csv"
            with holdings.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Ticker", "Name", "Weight", "Shares", "Market Value", "Asset Class", "Sector"])
                writer.writeheader()
                writer.writerows([
                    {"Ticker": "NVDA", "Name": "NVIDIA Corp", "Weight": "20", "Shares": "100", "Market Value": "1000", "Asset Class": "Equity", "Sector": "Information Technology"},
                    {"Ticker": "CASH", "Name": "Cash Collateral", "Weight": "2", "Asset Class": "Cash", "Sector": "Cash"},
                    {"Ticker": "SAP", "Name": "SAP SE", "Weight": "1", "Asset Class": "Equity", "Sector": "Technology"},
                ])
            task_key = {
                "task_id": "source_02_target_candidate_holdings_task_test",
                "source": "source_02_target_candidate_holdings",
                "params": {
                    "start": "2026-04-24",
                    "end": "2026-04-25",
                    "market_regime_etf_universe_path": str(universe),
                    "available_time": "2026-04-25T09:30:00-04:00",
                    "holding_feed_payloads": {"SMH": {"csv_path": str(holdings), "as_of_date": "2026-04-24"}},
                },
                "output_root": str(Path(tmp) / "task"),
            }
            module = import_module("data_source.source_02_target_candidate_holdings.pipeline")
            sql_writer = FakeSqlWriter()
            result = module.run(task_key, run_id="run", sql_writer=sql_writer)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["source_02_target_candidate_holdings"], 1)
            manifest = json.loads((Path(task_key["output_root"]) / "runs" / "run" / "request_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["model_layer_filter"], "layer_02_sector_context")
            self.assertEqual(manifest["universe_type_filter"], "sector_observation_etf")
            self.assertEqual(manifest["symbols"], ["SMH"])
            self.assertEqual(len(sql_writer.calls), 1)
            call = sql_writer.calls[0]
            self.assertEqual(call["table"], "source_02_target_candidate_holdings")
            self.assertEqual(call["key_columns"], ["etf_symbol", "as_of_date", "holding_symbol"])
            self.assertEqual(call["columns"], ["etf_symbol", "issuer_name", "universe_type", "exposure_type", "as_of_date", "available_time", "holding_symbol", "holding_name", "weight", "shares", "market_value", "sector_type"])
            rows = call["rows"]
            self.assertEqual(rows[0]["holding_symbol"], "NVDA")
            self.assertEqual(rows[0]["etf_symbol"], "SMH")
            self.assertEqual(rows[0]["universe_type"], "sector_observation_etf")
            self.assertEqual(rows[0]["exposure_type"], "industry_chain")
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
                "task_id": "source_02_target_candidate_default_feed_test",
                "source": "source_02_target_candidate_holdings",
                "params": {
                    "start": "2026-04-24",
                    "end": "2026-04-25",
                    "market_regime_etf_universe_path": str(universe),
                    "symbols": ["XLK"],
                    "holding_feed_payloads": {},
                },
                "output_root": str(Path(tmp) / "task"),
            }
            module = import_module("data_source.source_02_target_candidate_holdings.pipeline")
            captured = {}

            def fake_fetch(context):
                captured["params"] = context.task_key["params"]
                return module.StepResult("succeeded", [], {"feed_payloads": 1}), object()

            def fake_clean(context, payload):
                context.cleaned_dir.mkdir(parents=True, exist_ok=True)
                (context.cleaned_dir / "etf_holding_snapshot.jsonl").write_text(
                    json.dumps({"etf_symbol": "XLK", "holding_symbol": "MSFT", "holding_name": "Microsoft Corp", "asset_class": "Equity", "as_of_date": "2026-04-24"}) + "\n",
                    encoding="utf-8",
                )
                return module.StepResult("succeeded", [], {"etf_holding_snapshot": 1})

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
            self.assertEqual(writer.calls[0]["rows"][0]["holding_symbol"], "MSFT")

    def test_missing_window_holdings_are_reported_as_partial_coverage_not_failure(self):
        module = import_module("data_source.source_02_target_candidate_holdings.pipeline")
        task_key = {"task_id": "source_02_missing_window", "source": "source_02_target_candidate_holdings", "params": {"start": "2026-05-18", "end": "2026-05-19"}, "output_root": "/tmp/source_02_missing_window"}
        context = module.build_context(task_key, "run")
        payload = module.SourcePayload(
            universe_rows=[
                {"symbol": "ARKF", "issuer_name": "ARK Invest", "universe_type": "sector_observation_etf", "exposure_type": "thematic_growth"},
            ],
            selected_symbols=("ARKF",),
            raw_rows=[
                {"etf_symbol": "ARKF", "holding_symbol": "SHOP", "holding_name": "Shopify Inc", "asset_class": "Equity", "as_of_date": "2026-01-02"},
            ],
        )

        result, cleaned = module.clean(context, payload)

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.row_counts["source_02_target_candidate_holdings"], 0)
        self.assertEqual(cleaned.rows, [])
        self.assertEqual(result.details["missing_symbols"], ["ARKF"])
        self.assertIn("accepted_partial_coverage", result.details["missing_symbol_policy"])
        self.assertEqual(result.details["symbol_coverage"]["ARKF"]["outside_window"], 1)


if __name__ == "__main__":
    unittest.main()
