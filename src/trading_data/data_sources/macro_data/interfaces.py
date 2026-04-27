"""Macro data-kind interface defaults for the single ``macro_data`` bundle.

These entries are intentionally acquisition-facing. They provide a concrete
first request shape for each registered macro data kind so source wiring can be
smoked without inventing a separate bundle per agency/release.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MacroDataInterface:
    data_kind: str
    source: str
    endpoint_kind: str
    docs_url: str
    default_params: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


BLS_DOCS = "https://www.bls.gov/developers/api_signature_v2.htm"
CENSUS_DOCS = "https://www.census.gov/data/developers/guidance/api-user-guide.html"
BEA_DOCS = "https://apps.bea.gov/API/docs/index.htm"
FRED_DOCS = "https://fred.stlouisfed.org/docs/api/fred/"
TREASURY_DOCS = "https://fiscaldata.treasury.gov/api-documentation/"


def _release_stub(metric: str) -> dict[str, Any]:
    return {
        "metric": metric,
        "release_time": "2024-01-01T08:30:00-05:00",
        "effective_until": "",
    }


MACRO_INTERFACES: dict[str, MacroDataInterface] = {
    # BLS API v2. Series ids are smoke defaults, not final feature selections.
    "macro_bls_cpi": MacroDataInterface("macro_bls_cpi", "bls", "POST /publicAPI/v2/timeseries/data", BLS_DOCS, {**_release_stub("bls_cpi"), "series_ids": ["CUUR0000SA0"], "startyear": "2024", "endyear": "2024"}),
    "macro_bls_eci": MacroDataInterface("macro_bls_eci", "bls", "POST /publicAPI/v2/timeseries/data", BLS_DOCS, {**_release_stub("bls_eci"), "series_ids": ["CIU2010000000000A"], "startyear": "2024", "endyear": "2024"}),
    "macro_bls_employment_payrolls": MacroDataInterface("macro_bls_employment_payrolls", "bls", "POST /publicAPI/v2/timeseries/data", BLS_DOCS, {**_release_stub("bls_payrolls"), "series_ids": ["CES0000000001"], "startyear": "2024", "endyear": "2024"}),
    "macro_bls_import_export_prices": MacroDataInterface("macro_bls_import_export_prices", "bls", "POST /publicAPI/v2/timeseries/data", BLS_DOCS, {**_release_stub("bls_import_export_prices"), "series_ids": ["EIUIR"], "startyear": "2024", "endyear": "2024"}),
    "macro_bls_jolts": MacroDataInterface("macro_bls_jolts", "bls", "POST /publicAPI/v2/timeseries/data", BLS_DOCS, {**_release_stub("bls_jolts"), "series_ids": ["JTS000000000000000JOL"], "startyear": "2024", "endyear": "2024"}),
    "macro_bls_labor_force": MacroDataInterface("macro_bls_labor_force", "bls", "POST /publicAPI/v2/timeseries/data", BLS_DOCS, {**_release_stub("bls_unemployment_rate"), "series_ids": ["LNS14000000"], "startyear": "2024", "endyear": "2024"}),
    "macro_bls_ppi": MacroDataInterface("macro_bls_ppi", "bls", "POST /publicAPI/v2/timeseries/data", BLS_DOCS, {**_release_stub("bls_ppi"), "series_ids": ["WPUFD4"], "startyear": "2024", "endyear": "2024"}),
    "macro_bls_productivity": MacroDataInterface("macro_bls_productivity", "bls", "POST /publicAPI/v2/timeseries/data", BLS_DOCS, {**_release_stub("bls_productivity"), "series_ids": ["PRS85006092"], "startyear": "2024", "endyear": "2024"}),

    # Census economic indicator API shapes.
    "macro_census_retail_sales": MacroDataInterface("macro_census_retail_sales", "census", "GET /data/timeseries/eits/marts", CENSUS_DOCS, {**_release_stub("census_retail_sales"), "dataset": "timeseries/eits/marts", "get": "time,cell_value", "time": "2024"}),
    "macro_census_durable_goods": MacroDataInterface("macro_census_durable_goods", "census", "GET /data/timeseries/eits/m3", CENSUS_DOCS, {**_release_stub("census_durable_goods"), "dataset": "timeseries/eits/m3", "get": "time,cell_value", "time": "2024"}),
    "macro_census_construction_spending": MacroDataInterface("macro_census_construction_spending", "census", "GET /data/timeseries/eits/vip", CENSUS_DOCS, {**_release_stub("census_construction_spending"), "dataset": "timeseries/eits/vip", "get": "time,cell_value", "time": "2024"}),
    "macro_census_housing_construction": MacroDataInterface("macro_census_housing_construction", "census", "GET /data/timeseries/eits/resconst", CENSUS_DOCS, {**_release_stub("census_housing_construction"), "dataset": "timeseries/eits/resconst", "get": "time,cell_value", "time": "2024"}),
    "macro_census_new_home_sales": MacroDataInterface("macro_census_new_home_sales", "census", "GET /data/timeseries/eits/newresconst", CENSUS_DOCS, {**_release_stub("census_new_home_sales"), "dataset": "timeseries/eits/newresconst", "get": "time,cell_value", "time": "2024"}),
    "macro_census_manufacturing_orders": MacroDataInterface("macro_census_manufacturing_orders", "census", "GET /data/timeseries/eits/m3", CENSUS_DOCS, {**_release_stub("census_manufacturing_orders"), "dataset": "timeseries/eits/m3", "get": "time,cell_value", "time": "2024"}),
    "macro_census_international_trade": MacroDataInterface("macro_census_international_trade", "census", "GET /data/timeseries/eits/ftd", CENSUS_DOCS, {**_release_stub("census_international_trade"), "dataset": "timeseries/eits/ftd", "get": "time,cell_value", "time": "2024"}),
    "macro_census_wholesale_trade": MacroDataInterface("macro_census_wholesale_trade", "census", "GET /data/timeseries/eits/mwts", CENSUS_DOCS, {**_release_stub("census_wholesale_trade"), "dataset": "timeseries/eits/mwts", "get": "time,cell_value", "time": "2024"}),
    "macro_census_business_formation": MacroDataInterface("macro_census_business_formation", "census", "GET /data/timeseries/bfs", CENSUS_DOCS, {**_release_stub("census_business_formation"), "dataset": "timeseries/bfs", "get": "time,cell_value", "time": "2024"}),

    # BEA API dataset names.
    "macro_bea_nipa": MacroDataInterface("macro_bea_nipa", "bea", "GET /api/data DatasetName=NIPA", BEA_DOCS, {**_release_stub("bea_nipa"), "api_params": {"method": "GetData", "DatasetName": "NIPA", "TableName": "T10101", "Frequency": "Q", "Year": "2024"}}),
    "macro_bea_pce_income_outlays": MacroDataInterface("macro_bea_pce_income_outlays", "bea", "GET /api/data DatasetName=NIPA", BEA_DOCS, {**_release_stub("bea_pce_income_outlays"), "api_params": {"method": "GetData", "DatasetName": "NIPA", "TableName": "T20804", "Frequency": "M", "Year": "2024"}}),
    "macro_bea_fixed_assets": MacroDataInterface("macro_bea_fixed_assets", "bea", "GET /api/data DatasetName=FixedAssets", BEA_DOCS, {**_release_stub("bea_fixed_assets"), "api_params": {"method": "GetData", "DatasetName": "FixedAssets", "TableName": "FAAt101", "Year": "2023"}}),
    "macro_bea_gdp_by_industry": MacroDataInterface("macro_bea_gdp_by_industry", "bea", "GET /api/data DatasetName=GDPbyIndustry", BEA_DOCS, {**_release_stub("bea_gdp_by_industry"), "api_params": {"method": "GetData", "DatasetName": "GDPbyIndustry", "TableID": "1", "Frequency": "A", "Year": "2023"}}),
    "macro_bea_international_accounts": MacroDataInterface("macro_bea_international_accounts", "bea", "GET /api/data DatasetName=ITA", BEA_DOCS, {**_release_stub("bea_international_accounts"), "api_params": {"method": "GetData", "DatasetName": "ITA", "Indicator": "BalGds", "Frequency": "Q", "Year": "2024"}}),
    "macro_bea_regional": MacroDataInterface("macro_bea_regional", "bea", "GET /api/data DatasetName=Regional", BEA_DOCS, {**_release_stub("bea_regional"), "api_params": {"method": "GetData", "DatasetName": "Regional", "TableName": "SAGDP9N", "LineCode": "1", "GeoFips": "00000", "Year": "2023"}}),

    # FRED/ALFRED. FRED is only for FRED-native/approved series by policy.
    "macro_fred_native": MacroDataInterface("macro_fred_native", "fred", "GET /fred/series/observations", FRED_DOCS, {**_release_stub("fred_native"), "endpoint": "series/observations", "series_id": "DGS10", "api_params": {"observation_start": "2024-01-01", "observation_end": "2024-01-10"}}),
    "macro_alfred_vintage": MacroDataInterface("macro_alfred_vintage", "fred", "GET /fred/series/vintagedates", FRED_DOCS, {**_release_stub("alfred_vintage"), "endpoint": "series/vintagedates", "series_id": "GDP", "api_params": {"limit": "10"}}),

    # U.S. Treasury Fiscal Data endpoints.
    "macro_treasury_debt": MacroDataInterface("macro_treasury_debt", "us_treasury_fiscal_data", "GET /v2/accounting/od/debt_to_penny", TREASURY_DOCS, {**_release_stub("treasury_debt"), "endpoint": "v2/accounting/od/debt_to_penny", "api_params": {"sort": "-record_date"}, "page_size": 1}),
    "macro_treasury_dts": MacroDataInterface("macro_treasury_dts", "us_treasury_fiscal_data", "GET /v1/accounting/dts/dts_table_1", TREASURY_DOCS, {**_release_stub("treasury_dts"), "endpoint": "v1/accounting/dts/dts_table_1", "api_params": {"sort": "-record_date"}, "page_size": 1}),
    "macro_treasury_interest_rates": MacroDataInterface("macro_treasury_interest_rates", "us_treasury_fiscal_data", "GET /v2/accounting/od/avg_interest_rates", TREASURY_DOCS, {**_release_stub("treasury_interest_rates"), "endpoint": "v2/accounting/od/avg_interest_rates", "api_params": {"sort": "-record_date"}, "page_size": 1}),
    "macro_treasury_interest_expense": MacroDataInterface("macro_treasury_interest_expense", "us_treasury_fiscal_data", "GET /v2/accounting/od/interest_expense", TREASURY_DOCS, {**_release_stub("treasury_interest_expense"), "endpoint": "v2/accounting/od/interest_expense", "api_params": {"sort": "-record_date"}, "page_size": 1}),
    "macro_treasury_mts": MacroDataInterface("macro_treasury_mts", "us_treasury_fiscal_data", "GET /v1/accounting/mts/mts_table_1", TREASURY_DOCS, {**_release_stub("treasury_mts"), "endpoint": "v1/accounting/mts/mts_table_1", "api_params": {"sort": "-record_date"}, "page_size": 1}),

    # Release calendars are intentionally marked adapter-needed until official page adapters are chosen.
    "macro_release_calendar": MacroDataInterface("macro_release_calendar", "official_macro_release_calendar", "official agency calendar page/API", "", {}, ("Owned by trading-execution calendar_discovery; no universal API assumed.",)),
}


def params_for_data_kind(data_kind: str) -> dict[str, Any]:
    interface = MACRO_INTERFACES[data_kind]
    return {"source": interface.source, "data_kind": data_kind, **interface.default_params}
