"""Registered feed availability candidates.

Names intentionally mirror the project docs instead of introducing new feed
or data_kind vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedCandidate:
    feed: str
    display_name: str
    data_kind_candidates: tuple[str, ...]
    access: str
    secret_alias: str | None
    docs_url: str


FEEDS: dict[str, FeedCandidate] = {
    "us_treasury_fiscal_data": FeedCandidate(
        feed="us_treasury_fiscal_data",
        display_name="U.S. Treasury Fiscal Data",
        data_kind_candidates=(
            "macro Treasury Fiscal Data",
            "debt",
            "interest rates",
        ),
        access="open/no-key",
        secret_alias=None,
        docs_url="https://fiscaldata.treasury.gov/api-documentation/",
    ),
    "sec_edgar": FeedCandidate(
        feed="sec_edgar",
        display_name="SEC EDGAR",
        data_kind_candidates=(
            "SEC EDGAR company financial data",
            "submissions",
            "company facts",
        ),
        access="open/no-key with identifying User-Agent",
        secret_alias=None,
        docs_url="https://www.sec.gov/edgar/sec-api-documentation",
    ),
    "fomc_calendar": FeedCandidate(
        feed="fomc_calendar",
        display_name="Federal Reserve FOMC page",
        data_kind_candidates=("FOMC and economic release calendar data",),
        access="open/no-key",
        secret_alias=None,
        docs_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    ),
    "census": FeedCandidate(
        feed="census",
        display_name="Census",
        data_kind_candidates=("macro Census data", "retail sales"),
        access="public API; optional key",
        secret_alias="census",
        docs_url="https://www.census.gov/data/developers/guidance/api-user-guide.html",
    ),
    "bea": FeedCandidate(
        feed="bea",
        display_name="BEA",
        data_kind_candidates=("macro BEA data", "NIPA/GDP", "PCE"),
        access="API key through BEA_SECRET_ALIAS",
        secret_alias="bea",
        docs_url="https://apps.bea.gov/API/docs/index.htm",
    ),
    "bls": FeedCandidate(
        feed="bls",
        display_name="BLS",
        data_kind_candidates=("macro BLS data", "CPI", "CES payrolls"),
        access="public API; optional key",
        secret_alias="bls",
        docs_url="https://www.bls.gov/developers/api_signature_v2.htm",
    ),
    "fred": FeedCandidate(
        feed="fred",
        display_name="FRED / St. Louis Fed",
        data_kind_candidates=("FRED-native and ALFRED/vintage data",),
        access="API key through FRED_SECRET_ALIAS",
        secret_alias="fred",
        docs_url="https://fred.stlouisfed.org/docs/api/fred/",
    ),
    "alpaca": FeedCandidate(
        feed="alpaca",
        display_name="Alpaca",
        data_kind_candidates=(
            "equity market data",
            "bars",
            "quotes",
            "trades",
            "news",
        ),
        access="API key through ALPACA_SECRET_ALIAS",
        secret_alias="alpaca",
        docs_url="https://docs.alpaca.markets/",
    ),
    "thetadata": FeedCandidate(
        feed="thetadata",
        display_name="ThetaData",
        data_kind_candidates=(
            "option data",
            "option contracts",
            "quotes/NBBO",
            "OHLC",
            "open interest",
            "Greeks",
        ),
        access="local Theta Terminal and optional feed alias",
        secret_alias="thetadata",
        docs_url="https://http-docs.thetadata.us/",
    ),
    "okx": FeedCandidate(
        feed="okx",
        display_name="OKX",
        data_kind_candidates=("crypto market data", "crypto bars", "tickers"),
        access="public market endpoints for market data",
        secret_alias="okx",
        docs_url="https://www.okx.com/docs-v5/en/",
    ),
}


STATUS_FIELDS = (
    "feed",
    "status",
    "http_status",
    "available",
    "skipped_reason",
    "error_type",
    "response_shape_keys",
    "sample_rows",
)
