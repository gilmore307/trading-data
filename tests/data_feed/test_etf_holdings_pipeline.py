import csv
import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from importlib import import_module

run = import_module("data_feed.06_feed_etf_holdings.pipeline").run


class EtfHoldingsPipelineTests(unittest.TestCase):
    def test_parse_issuer_csv_snapshot(self):
        csv_text = """Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Shares,CUSIP
NVDA,NVIDIA Corp,Information Technology,Equity,"$100,000",18.53%,1234,67066G104
AAPL,Apple Inc,Information Technology,Equity,"$90,000",15.85%,1000,037833100
"""
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "06_feed_etf_holdings_task_test",
                "feed": "06_feed_etf_holdings",
                "params": {
                    "etf_symbol": "VGT",
                    "issuer_name": "vanguard",
                    "as_of_date": "2026-04-24",
                    "source_url": "https://investor.vanguard.com/investment-products/etfs/profile/vgt",
                    "csv_text": csv_text,
                },
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.row_counts["etf_holding_snapshot"], 2)
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "etf_holding_snapshot.csv"
            with saved.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["etf_symbol"], "VGT")
            self.assertEqual(rows[0]["holding_symbol"], "NVDA")
            self.assertEqual(rows[0]["weight"], "18.53")
            self.assertEqual(rows[0]["market_value"], "100000")
            receipt = json.loads((Path(task_key["output_root"]) / "completion_receipt.json").read_text())
            self.assertEqual(receipt["runs"][0]["status"], "succeeded")

    def test_parse_html_holdings_table(self):
        html = """
        <table>
          <tr><th>Ticker</th><th>Holdings</th><th>CUSIP</th><th>SEDOL</th><th>% of fund</th><th>Shares</th><th>Market value</th></tr>
          <tr><td>NVDA</td><td>NVIDIA Corp.</td><td>67066G104</td><td>2379504</td><td>18.53 %</td><td>129,246,346</td><td>$22,540,562,742</td></tr>
        </table>
        """
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "06_feed_etf_holdings_html_test",
                "feed": "06_feed_etf_holdings",
                "params": {"etf_symbol": "VGT", "issuer_name": "vanguard", "as_of_date": "2026-04-24", "html": html},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "etf_holding_snapshot.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["holding_name"], "NVIDIA Corp.")
            self.assertEqual(row["sedol"], "2379504")
            self.assertEqual(row["shares"], "129246346")

    def test_parse_xlsx_holdings_table(self):
        workbook = _minimal_xlsx([
            ["Ticker", "Name", "Weight (%)", "Shares", "Market Value", "Asset Class"],
            ["NVDA", "NVIDIA Corp", "18.5", "100", "1000", "Equity"],
        ])
        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "holdings.xlsx"
            xlsx_path.write_bytes(workbook)
            task_key = {
                "task_id": "06_feed_etf_holdings_xlsx_test",
                "feed": "06_feed_etf_holdings",
                "params": {"etf_symbol": "XLK", "issuer_name": "State Street / SPDR", "as_of_date": "2026-04-24", "xlsx_path": str(xlsx_path)},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "etf_holding_snapshot.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["holding_symbol"], "NVDA")
            self.assertEqual(row["asset_class"], "Equity")

    def test_parse_first_trust_html_holdings_table(self):
        html = """
        <table>
          <tr><td>Security Name</td><td>Identifier</td><td>CUSIP</td><td>Classification</td><td>Shares / Quantity</td><td>Market Value</td><td>Weighting</td></tr>
          <tr><td>Palo Alto Networks, Inc.</td><td>PANW</td><td>697435105</td><td>Software and Computer Services</td><td>5,045,731</td><td>$1,225,254,858.73</td><td>10.21%</td></tr>
        </table>
        """
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "06_feed_etf_holdings_first_trust_html_test",
                "feed": "06_feed_etf_holdings",
                "params": {"etf_symbol": "CIBR", "issuer_name": "First Trust", "as_of_date": "2026-05-18", "html": html},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "etf_holding_snapshot.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["holding_symbol"], "PANW")
            self.assertEqual(row["holding_name"], "Palo Alto Networks, Inc.")
            self.assertEqual(row["sector_type"], "Software and Computer Services")
            self.assertEqual(row["shares"], "5045731")
            self.assertEqual(row["weight"], "10.21")

    def test_parse_blackrock_ishares_json_holdings_vectors(self):
        payload = {
            "componentsByNameMap": {
                "holdings": {
                    "containersByNameMap": {
                        "all": {
                            "dataPointsByNameMap": {
                                "asOfDate": {"value": 20260515, "formattedValue": "May 15, 2026"},
                                "ticker": {"value": ["UNP", "UBER"]},
                                "issueName": {"value": ["UNION PACIFIC CORP", "UBER TECHNOLOGIES INC"]},
                                "holdingPercent": {"value": [16.81251, 16.18381]},
                                "unitsHeld": {"value": [1336490, 4635488]},
                                "marketValue": {"value": [361600734.4, 348078793.92]},
                                "cusip": {"value": ["907818108", "90353T100"]},
                                "sedol": {"value": ["2914734", "BK6N347"]},
                                "assetClass": {"value": ["Equity", "Equity"]},
                                "sectorName": {"value": ["Industrials", "Industrials"]},
                            }
                        }
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                "task_id": "06_feed_etf_holdings_blackrock_json_test",
                "feed": "06_feed_etf_holdings",
                "params": {"etf_symbol": "IYT", "issuer_name": "BlackRock / iShares", "json_text": json.dumps(payload)},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "etf_holding_snapshot.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["issuer_name"], "blackrock_ishares")
            self.assertEqual(row["as_of_date"], "2026-05-15")
            self.assertEqual(row["holding_symbol"], "UNP")
            self.assertEqual(row["weight"], "16.81251")
            self.assertEqual(row["shares"], "1336490")
            self.assertEqual(row["sector_type"], "Industrials")

    def test_parse_vaneck_xlsx_as_of_and_holdings_columns(self):
        workbook = _minimal_xlsx([
            ["Daily Holdings (%)  05/15/2026", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", "", ""],
            ["Number", "Ticker", "Holding Name", "Identifier (FIGI)", "Shares", "Asset Class", "Market Value (US$)", "Notional Value", "% of Net Assets"],
            ["1", "NVDA", "Nvidia Corp", "BBG000BBJQV0", "49,231,461", "Stock", "$11,092,832,792.52", "--", "17.50%"],
        ])
        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "holdings.xlsx"
            xlsx_path.write_bytes(workbook)
            task_key = {
                "task_id": "06_feed_etf_holdings_vaneck_xlsx_test",
                "feed": "06_feed_etf_holdings",
                "params": {"etf_symbol": "SMH", "issuer_name": "VanEck", "xlsx_path": str(xlsx_path)},
                "output_root": str(Path(tmp) / "task"),
            }
            result = run(task_key, run_id="run")
            self.assertEqual(result.status, "succeeded")
            saved = Path(task_key["output_root"]) / "runs" / "run" / "saved" / "etf_holding_snapshot.csv"
            with saved.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["as_of_date"], "2026-05-15")
            self.assertEqual(row["holding_symbol"], "NVDA")
            self.assertEqual(row["holding_name"], "Nvidia Corp")
            self.assertEqual(row["weight"], "17.50")
            self.assertEqual(row["market_value"], "11092832792.52")

    def test_default_official_urls_cover_spdr_global_x_ark_and_first_trust(self):
        module = import_module("data_feed.06_feed_etf_holdings.pipeline")

        self.assertEqual(
            module._default_source_url("XLK", "state_street_/_spdr", {"as_of_date": "2026-05-18"}),
            "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-xlk.xlsx",
        )
        self.assertEqual(
            module._default_source_url("AIQ", "global_x", {"as_of_date": "2026-05-18"}),
            "https://assets.globalxetfs.com/funds/holdings/aiq_full-holdings_20260518.csv",
        )
        self.assertIn("ARK_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.csv", module._default_source_url("ARKF", "ark_invest", {}))
        self.assertEqual(
            module._default_source_url("CIBR", "first_trust", {}),
            "https://www.ftportfolios.com/Retail/Etf/EtfHoldings.aspx?Ticker=CIBR",
        )
        self.assertIn("portfolioId=239771", module._default_source_url("IGV", "blackrock_ishares", {}))
        self.assertIn("portfolioId=239501", module._default_source_url("IYT", "blackrock_ishares", {}))
        self.assertEqual(
            module._default_source_url("SMH", "vaneck", {}),
            "https://www.vaneck.com/us/en/etf/equity/smh/holdings/download/xlsx/",
        )


def _minimal_xlsx(rows: list[list[str]]) -> bytes:
    strings: list[str] = []
    indexes: dict[str, int] = {}
    cells = []
    for row_index, row in enumerate(rows, start=1):
        row_cells = []
        for col_index, value in enumerate(row):
            if value not in indexes:
                indexes[value] = len(strings)
                strings.append(value)
            col = chr(ord("A") + col_index)
            row_cells.append(f'<c r="{col}{row_index}" t="s"><v>{indexes[value]}</v></c>')
        cells.append(f'<row r="{row_index}">{"".join(row_cells)}</row>')
    shared = '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + "".join(f"<si><t>{value}</t></si>" for value in strings) + "</sst>"
    sheet = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(cells) + "</sheetData></worksheet>"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        archive.writestr("xl/sharedStrings.xml", shared)
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
