"""Bounded provider/data-kind interface probes."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from source_availability.http import HttpClient, HttpResult
from source_availability.report import ProbeResult
from source_availability.sanitize import sample_rows, sanitize_url, sanitize_value, shape_keys
from collections.abc import Mapping
from source_availability.secrets import load_secret_alias, public_secret_summary

from .catalog import DataKindInterface, INTERFACES


def _candidate_like(interface: DataKindInterface):
    # ProbeResult.skipped expects SourceCandidate-like attributes. Keep this local
    # so source_interfaces does not depend on source_availability registry names.
    class Candidate:
        source = interface.source
        display_name = interface.source
        data_kind_candidates = (interface.data_kind,)
        access = interface.access
        secret_alias = None
        docs_url = interface.docs_url or ""
    return Candidate()


def _safe_samples(payload: Any, row_path: tuple[str, ...]) -> list[Any]:
    if row_path:
        return sample_rows(payload, row_path=row_path, limit=2)
    if isinstance(payload, Mapping):
        shallow = {key: value for key, value in payload.items() if not isinstance(value, (dict, list, tuple))}
        return [sanitize_value(shallow)] if shallow else []
    return sample_rows(payload, limit=2)


def _result(interface: DataKindInterface, http: HttpResult, payload: Any, *, row_path: tuple[str, ...] = (), notes: list[str] | None = None, secret_alias: dict[str, Any] | None = None) -> ProbeResult:
    ok = http.status is not None and 200 <= http.status < 300
    return ProbeResult(
        source=interface.source,
        status="ok" if ok else "failed",
        available=ok,
        data_kind_candidates=[interface.data_kind],
        access=interface.access,
        docs_url=interface.docs_url or "",
        endpoint=sanitize_url(http.url),
        http_status=http.status,
        response_shape_keys=shape_keys(payload),
        sample_rows=_safe_samples(payload, row_path),
        secret_alias=secret_alias,
        error_type=http.error_type,
        error_message=http.error_message,
        notes=[*(notes or []), *interface.notes],
    )


def _json(http: HttpResult) -> Any:
    try:
        return sanitize_value(json.loads(http.body.decode("utf-8")))
    except json.JSONDecodeError:
        return {"text_sample": http.text()[:500]}


def probe_interface(interface: DataKindInterface, client: HttpClient, *, sec_user_agent: str) -> ProbeResult:
    if interface.source == "alpaca":
        return _probe_alpaca(interface, client)
    if interface.source == "okx":
        return _probe_okx(interface, client)
    if interface.source == "thetadata":
        return _probe_thetadata(interface, client)
    if interface.source == "08_source_sec_company_financials":
        return _probe_sec(interface, client, sec_user_agent=sec_user_agent)
    if interface.source == "fomc_calendar":
        return _probe_fomc(interface, client)
    return ProbeResult.skipped(_candidate_like(interface), "no executable interface probe yet")


def _probe_alpaca(interface: DataKindInterface, client: HttpClient) -> ProbeResult:
    secret = load_secret_alias("alpaca")
    summary = public_secret_summary(secret)
    api_key = secret.values.get("api_key")
    secret_key = secret.values.get("secret_key")
    if not api_key or not secret_key:
        return ProbeResult.skipped(_candidate_like(interface), "missing Alpaca api_key/secret_key alias", secret_alias=summary)
    base = str(secret.values.get("data_endpoint") or "https://data.alpaca.markets").rstrip("/")
    headers = {"APCA-API-KEY-ID": str(api_key), "APCA-API-SECRET-KEY": str(secret_key)}
    symbol = str(interface.smoke_params.get("symbol") or interface.smoke_params.get("symbols") or "AAPL")
    if interface.data_kind == "equity_bar":
        http = client.get(f"{base}/v2/stocks/{symbol}/bars", params={"timeframe": "1Day", "start": "2024-01-02T00:00:00Z", "end": "2024-01-04T00:00:00Z", "limit": "2", "adjustment": "raw"}, headers=headers)
        return _result(interface, http, _json(http), row_path=("bars",), secret_alias=summary)
    if interface.data_kind == "equity_trade":
        http = client.get(f"{base}/v2/stocks/{symbol}/trades", params={"start": "2024-01-02T14:30:00Z", "end": "2024-01-02T14:31:00Z", "limit": "2"}, headers=headers)
        return _result(interface, http, _json(http), row_path=("trades",), secret_alias=summary)
    if interface.data_kind == "equity_quote":
        http = client.get(f"{base}/v2/stocks/{symbol}/quotes", params={"start": "2024-01-02T14:30:00Z", "end": "2024-01-02T14:31:00Z", "limit": "2"}, headers=headers)
        return _result(interface, http, _json(http), row_path=("quotes",), secret_alias=summary)
    if interface.data_kind == "equity_snapshot":
        http = client.get(f"{base}/v2/stocks/{symbol}/snapshot", headers=headers)
        return _result(interface, http, _json(http), secret_alias=summary)
    if interface.data_kind == "equity_news":
        http = client.get(f"{base}/v1beta1/news", params={"symbols": symbol, "start": "2024-01-02T00:00:00Z", "end": "2024-01-10T00:00:00Z", "limit": "2"}, headers=headers)
        return _result(interface, http, _json(http), row_path=("news",), secret_alias=summary)
    return ProbeResult.skipped(_candidate_like(interface), "unsupported Alpaca data_kind")


def _probe_okx(interface: DataKindInterface, client: HttpClient) -> ProbeResult:
    inst_id = str(interface.smoke_params.get("instId") or "BTC-USDT")
    headers = {"User-Agent": "trading-data-source-interfaces/0.1", "Accept": "application/json"}
    if interface.data_kind == "crypto_bar":
        http = client.get("https://www.okx.com/api/v5/market/candles", params={"instId": inst_id, "bar": "1D", "limit": "2"}, headers=headers)
    elif interface.data_kind == "crypto_trade":
        http = client.get("https://www.okx.com/api/v5/market/trades", params={"instId": inst_id, "limit": "2"}, headers=headers)
    elif interface.data_kind == "crypto_quote":
        http = client.get("https://www.okx.com/api/v5/market/ticker", params={"instId": inst_id}, headers=headers)
    elif interface.data_kind == "crypto_order_book":
        http = client.get("https://www.okx.com/api/v5/market/books", params={"instId": inst_id, "sz": "2"}, headers=headers)
    else:
        return ProbeResult.skipped(_candidate_like(interface), "unsupported OKX data_kind")
    return _result(interface, http, _json(http), row_path=("data",))


def _probe_thetadata(interface: DataKindInterface, client: HttpClient) -> ProbeResult:
    secret = load_secret_alias("thetadata")
    summary = public_secret_summary(secret)
    base = "http://127.0.0.1:25503"
    endpoint = interface.endpoint_kind.split(" ", 1)[1]
    params = _thetadata_params(interface)
    http = client.get(base + endpoint, params=params)
    if http.status is None:
        return ProbeResult(
            source=interface.source,
            status="skipped",
            available=False,
            data_kind_candidates=[interface.data_kind],
            access=interface.access,
            docs_url=interface.docs_url or "",
            endpoint=sanitize_url(http.url),
            http_status=http.status,
            secret_alias=summary,
            skipped_reason="Theta Terminal not reachable on 127.0.0.1:25503",
            error_type=http.error_type,
            error_message=http.error_message,
            notes=list(interface.notes),
        )
    payload = _json(http)
    if http.status == 403 and "professional subscription" in http.text().lower():
        return ProbeResult(
            source=interface.source,
            status="skipped",
            available=False,
            data_kind_candidates=[interface.data_kind],
            access=interface.access,
            docs_url=interface.docs_url or "",
            endpoint=sanitize_url(http.url),
            http_status=http.status,
            secret_alias=summary,
            skipped_reason="ThetaData account entitlement requires professional subscription",
            error_type=http.error_type,
            error_message="entitlement blocked",
            response_shape_keys=shape_keys(payload),
            sample_rows=_safe_samples(payload, ()),
            notes=list(interface.notes),
        )
    return _result(interface, http, payload, row_path=("response",), secret_alias=summary)


def _thetadata_params(interface: DataKindInterface) -> dict[str, str]:
    # Known liquid AAPL option/date selected from live list/contracts smoke so
    # history trade/quote/OHLC endpoints return real rows under STANDARD options.
    contract = {
        "symbol": "AAPL",
        "expiration": "2026-05-15",
        "strike": "270.000",
        "right": "call",
        "format": "json",
    }
    one_day = {"start_date": "2026-04-24", "end_date": "2026-04-24"}
    if interface.data_kind == "option_contract":
        return {"symbol": "AAPL", "date": "2026-04-24", "format": "json"}
    if interface.data_kind in {"option_trade", "option_quote", "option_nbbo", "option_ohlc", "option_eod", "option_open_interest", "option_greeks_first_order", "option_greeks_second_order", "option_greeks_third_order", "option_trade_greeks"}:
        return {**contract, **one_day}
    if interface.data_kind in {"option_implied_volatility", "option_snapshot"}:
        return {"symbol": "AAPL", "expiration": "*", "format": "json"}
    return {k: str(v) for k, v in interface.smoke_params.items()}


def _probe_sec(interface: DataKindInterface, client: HttpClient, *, sec_user_agent: str) -> ProbeResult:
    headers = {"User-Agent": sec_user_agent, "Accept-Encoding": "identity"}
    cik = str(interface.smoke_params.get("cik") or "0000320193")
    if interface.data_kind == "sec_submission":
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        http = client.get(url, headers=headers)
        payload = _json(http)
        # Flatten one recent filing row for visibility.
        recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload, dict) else {}
        if isinstance(recent, dict):
            payload = {"filing_recent": {key: value[0] for key, value in recent.items() if isinstance(value, list) and value}}
        return _result(interface, http, payload)
    if interface.data_kind == "sec_company_fact":
        http = client.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", headers=headers)
        return _result(interface, http, _json(http))
    if interface.data_kind == "sec_company_concept":
        taxonomy = str(interface.smoke_params.get("taxonomy") or "us-gaap")
        tag = str(interface.smoke_params.get("tag") or "Assets")
        http = client.get(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json", headers=headers)
        return _result(interface, http, _json(http), row_path=("units", "USD"))
    if interface.data_kind == "sec_xbrl_frame":
        http = client.get("https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/CY2023Q4I.json", headers=headers)
        return _result(interface, http, _json(http), row_path=("data",))
    return ProbeResult.skipped(_candidate_like(interface), "unsupported SEC data_kind")


def _probe_fomc(interface: DataKindInterface, client: HttpClient) -> ProbeResult:
    http = client.get(interface.docs_url or "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    text = http.text()
    title_match = re.search(r"<title>(.*?)</title>", text, flags=re.I | re.S)
    payload = {"title": re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else None, "contains_FOMC": "FOMC" in text, "bytes_read": len(http.body)}
    return _result(interface, http, payload)


def probe_many(data_kinds: list[str] | None, source: str | None, client: HttpClient, *, sec_user_agent: str) -> list[ProbeResult]:
    selected = [item for item in INTERFACES.values() if (not source or item.source == source) and (not data_kinds or item.data_kind in data_kinds)]
    return [probe_interface(item, client, sec_user_agent=sec_user_agent) for item in selected]


def interface_payload() -> list[dict[str, Any]]:
    return [asdict(item) for item in sorted(INTERFACES.values(), key=lambda value: (value.source, value.data_kind))]
