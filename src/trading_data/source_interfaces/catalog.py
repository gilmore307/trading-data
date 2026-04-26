"""Concrete provider/data-kind interface inventory.

This catalog is intentionally practical: it records the first endpoint/parameter
shape we can use to discover actual provider responses. It is not a final
storage schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DataKindInterface:
    data_kind: str
    source: str
    bundle: str
    endpoint_kind: str
    docs_url: str | None
    access: str
    smoke_params: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


INTERFACES: dict[str, DataKindInterface] = {
    # Alpaca stock/ETF market data.
    "equity_bar": DataKindInterface(
        "equity_bar", "alpaca", "alpaca_bars", "GET /v2/stocks/{symbol}/bars",
        "https://docs.alpaca.markets/reference/stockbars", "api-key", {"symbol": "AAPL"},
    ),
    "equity_trade": DataKindInterface(
        "equity_trade", "alpaca", "alpaca_liquidity", "GET /v2/stocks/{symbol}/trades",
        "https://docs.alpaca.markets/reference/stocktrades", "api-key", {"symbol": "AAPL"},
    ),
    "equity_quote": DataKindInterface(
        "equity_quote", "alpaca", "alpaca_liquidity", "GET /v2/stocks/{symbol}/quotes",
        "https://docs.alpaca.markets/reference/stockquotes-1", "api-key", {"symbol": "AAPL"},
    ),
    "equity_snapshot": DataKindInterface(
        "equity_snapshot", "alpaca", "alpaca_liquidity", "GET /v2/stocks/{symbol}/snapshot",
        "https://docs.alpaca.markets/reference/stocksnapshots-1", "api-key", {"symbol": "AAPL"},
    ),
    "equity_news": DataKindInterface(
        "equity_news", "alpaca", "alpaca_news", "GET /v1beta1/news",
        "https://docs.alpaca.markets/reference/news-3", "api-key", {"symbols": "AAPL"},
    ),
    # OKX public market data.
    "crypto_bar": DataKindInterface(
        "crypto_bar", "okx", "okx_bars", "GET /api/v5/market/candles",
        "https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-candlesticks", "open/no-key", {"instId": "BTC-USDT"},
    ),
    "crypto_trade": DataKindInterface(
        "crypto_trade", "okx", "okx_bars", "GET /api/v5/market/trades",
        "https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-trades", "open/no-key", {"instId": "BTC-USDT"},
    ),
    "crypto_quote": DataKindInterface(
        "crypto_quote", "okx", "okx_bars", "GET /api/v5/market/ticker",
        "https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-ticker", "open/no-key", {"instId": "BTC-USDT"},
    ),
    "crypto_order_book": DataKindInterface(
        "crypto_order_book", "okx", "okx_bars", "GET /api/v5/market/books",
        "https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-order-book", "open/no-key", {"instId": "BTC-USDT"},
    ),
    # ThetaData local terminal endpoints. These require the local terminal.
    "option_contract": DataKindInterface(
        "option_contract", "thetadata", "thetadata_option_1m_bundle", "GET /v3/option/list/contracts/quote",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL", "date": "2026-04-24"},
        ("Requires Theta Terminal on localhost:25503 and entitlement validation.",),
    ),
    "option_trade": DataKindInterface(
        "option_trade", "thetadata", "thetadata_option_1m_bundle", "GET /v3/option/history/trade",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_quote": DataKindInterface(
        "option_quote", "thetadata", "thetadata_option_1m_bundle", "GET /v3/option/history/quote",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_nbbo": DataKindInterface(
        "option_nbbo", "thetadata", "thetadata_option_1m_bundle", "GET /v3/option/history/trade_quote",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_ohlc": DataKindInterface(
        "option_ohlc", "thetadata", "thetadata_option_1m_bundle", "GET /v3/option/history/ohlc",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL", "start_date": "2026-04-24", "end_date": "2026-04-24"},
    ),
    "option_eod": DataKindInterface(
        "option_eod", "thetadata", "thetadata_option_1m_bundle", "GET /v3/option/history/eod",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_open_interest": DataKindInterface(
        "option_open_interest", "thetadata", "thetadata_option_snapshot_bundle", "GET /v3/option/history/open_interest",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_implied_volatility": DataKindInterface(
        "option_implied_volatility", "thetadata", "thetadata_option_snapshot_bundle", "GET /v3/option/snapshot/greeks/implied_volatility",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_greeks_first_order": DataKindInterface(
        "option_greeks_first_order", "thetadata", "thetadata_option_snapshot_bundle", "GET /v3/option/snapshot/greeks/first_order",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_greeks_second_order": DataKindInterface(
        "option_greeks_second_order", "thetadata", "thetadata_option_1m_bundle", "GET /v3/option/history/greeks/second_order",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_greeks_third_order": DataKindInterface(
        "option_greeks_third_order", "thetadata", "thetadata_option_1m_bundle", "GET /v3/option/history/greeks/third_order",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_trade_greeks": DataKindInterface(
        "option_trade_greeks", "thetadata", "thetadata_option_1m_bundle", "GET /v3/option/history/trade_greeks/first_order",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    "option_snapshot": DataKindInterface(
        "option_snapshot", "thetadata", "thetadata_option_snapshot_bundle", "GET /v3/option/snapshot/quote",
        "https://http-docs.thetadata.us/", "local-terminal", {"symbol": "AAPL"},
    ),
    # SEC EDGAR open APIs.
    "sec_submission": DataKindInterface(
        "sec_submission", "sec_company_financials", "sec_company_financials", "GET submissions/CIK##########.json",
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces", "open/user-agent", {"cik": "0000320193"},
    ),
    "sec_company_fact": DataKindInterface(
        "sec_company_fact", "sec_company_financials", "sec_company_financials", "GET api/xbrl/companyfacts/CIK##########.json",
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces", "open/user-agent", {"cik": "0000320193"},
    ),
    "sec_company_concept": DataKindInterface(
        "sec_company_concept", "sec_company_financials", "sec_company_financials", "GET api/xbrl/companyconcept/CIK##########/us-gaap/Assets.json",
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces", "open/user-agent", {"cik": "0000320193", "taxonomy": "us-gaap", "tag": "Assets"},
    ),
    "sec_xbrl_frame": DataKindInterface(
        "sec_xbrl_frame", "sec_company_financials", "sec_company_financials", "GET api/xbrl/frames/us-gaap/Assets/USD/CY2023Q4I.json",
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces", "open/user-agent", {},
    ),
    # Calendar/web discovery.
    "fomc_meeting": DataKindInterface(
        "fomc_meeting", "fomc_calendar", "calendar_discovery", "GET official Federal Reserve FOMC page",
        "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "open/no-key", {},
    ),
    "economic_release_calendar": DataKindInterface(
        "economic_release_calendar", "official_macro_release_calendar", "calendar_discovery", "official agency calendar page/API", None, "web-discovery", {},
        ("Requires source-specific official calendar adapters; not a universal API.",),
    ),
    "etf_holding": DataKindInterface(
        "etf_holding", "etf_issuer_holdings", "etf_holdings", "issuer-published holdings file/page", None, "web/file", {},
        ("Requires issuer-specific adapters; no universal ETF holdings API assumed.",),
    ),
}


def list_interfaces(source: str | None = None) -> list[DataKindInterface]:
    values = sorted(INTERFACES.values(), key=lambda item: (item.source, item.data_kind))
    if source:
        values = [item for item in values if item.source == source]
    return values
