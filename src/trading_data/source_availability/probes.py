"""Concrete bounded source availability probes."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from .http import HttpClient, HttpResult
from .registry import SOURCES, SourceCandidate
from .report import ProbeResult
from .sanitize import sample_rows, sanitize_url, sanitize_value, shape_keys
from .secrets import load_secret_alias, public_secret_summary


ProbeFn = Callable[[HttpClient, str], ProbeResult]


def _json_probe_result(
    candidate: SourceCandidate,
    result: HttpResult,
    *,
    payload: Any,
    row_path: tuple[str, ...] = (),
    notes: list[str] | None = None,
    secret_alias: dict[str, Any] | None = None,
) -> ProbeResult:
    ok = result.status is not None and 200 <= result.status < 300
    return ProbeResult(
        source=candidate.source,
        status="ok" if ok else "failed",
        available=ok,
        data_kind_candidates=list(candidate.data_kind_candidates),
        access=candidate.access,
        docs_url=candidate.docs_url,
        endpoint=sanitize_url(result.url),
        http_status=result.status,
        response_shape_keys=shape_keys(payload),
        sample_rows=sample_rows(payload, row_path=row_path),
        secret_alias=secret_alias,
        error_type=result.error_type,
        error_message=result.error_message,
        notes=notes or [],
    )


def _parse_json_or_error(candidate: SourceCandidate, result: HttpResult) -> ProbeResult:
    try:
        payload = result.json()
    except json.JSONDecodeError as exc:
        error_type = result.error_type or type(exc).__name__
        error_message = result.error_message or str(exc)
        return ProbeResult(
            source=candidate.source,
            status="failed",
            available=False,
            data_kind_candidates=list(candidate.data_kind_candidates),
            access=candidate.access,
            docs_url=candidate.docs_url,
            endpoint=sanitize_url(result.url),
            http_status=result.status,
            error_type=error_type,
            error_message=error_message,
        )
    return _json_probe_result(candidate, result, payload=payload)


def probe_us_treasury_fiscal_data(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    del sec_user_agent
    candidate = SOURCES["us_treasury_fiscal_data"]
    result = client.get(
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny",
        params={"sort": "-record_date", "page[size]": "1"},
    )
    try:
        payload = result.json()
    except json.JSONDecodeError as exc:
        error = _parse_json_or_error(candidate, result)
        if not error.error_type:
            error.error_type = type(exc).__name__
            error.error_message = str(exc)
        return error
    return _json_probe_result(candidate, result, payload=payload, row_path=("data",))


def probe_sec_edgar(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    candidate = SOURCES["sec_edgar"]
    result = client.get(
        "https://data.sec.gov/submissions/CIK0000320193.json",
        headers={"User-Agent": sec_user_agent, "Accept-Encoding": "identity"},
    )
    try:
        payload = result.json()
    except json.JSONDecodeError:
        return _parse_json_or_error(candidate, result)
    rows = []
    recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload, dict) else {}
    if isinstance(recent, dict):
        rows = [sanitize_value({key: value[0] for key, value in recent.items() if isinstance(value, list) and value})]
    return ProbeResult(
        source=candidate.source,
        status="ok" if result.status and 200 <= result.status < 300 else "failed",
        available=bool(result.status and 200 <= result.status < 300),
        data_kind_candidates=list(candidate.data_kind_candidates),
        access=candidate.access,
        docs_url=candidate.docs_url,
        endpoint=sanitize_url(result.url),
        http_status=result.status,
        response_shape_keys=shape_keys(payload),
        sample_rows=rows[:1],
        error_type=result.error_type,
        error_message=result.error_message,
        notes=["Uses Apple CIK only as a tiny submissions shape smoke sample."],
    )


def probe_fomc_calendar(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    del sec_user_agent
    candidate = SOURCES["fomc_calendar"]
    result = client.get(candidate.docs_url)
    text = result.text()
    title_match = re.search(r"<title>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    h_keys = []
    if "FOMC" in text:
        h_keys.append("contains_FOMC")
    if "Meeting calendars" in text:
        h_keys.append("contains_meeting_calendars")
    sample = {
        "title": re.sub(r"\s+", " ", title_match.group(1)).strip()
        if title_match
        else None,
        "bytes_read": len(result.body),
    }
    ok = result.status is not None and 200 <= result.status < 300 and bool(h_keys)
    return ProbeResult(
        source=candidate.source,
        status="ok" if ok else "failed",
        available=ok,
        data_kind_candidates=list(candidate.data_kind_candidates),
        access=candidate.access,
        docs_url=candidate.docs_url,
        endpoint=sanitize_url(result.url),
        http_status=result.status,
        response_shape_keys=h_keys,
        sample_rows=[sanitize_value(sample)],
        error_type=result.error_type,
        error_message=result.error_message,
    )


def probe_census(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    del sec_user_agent
    candidate = SOURCES["census"]
    secret = load_secret_alias("census")
    params = {
        "get": "data_type_code,seasonally_adj,category_code,cell_value,error_data",
        "for": "us:*",
        "time": "2012",
    }
    if secret.values.get("api_key"):
        params["key"] = str(secret.values["api_key"])
    result = client.get("https://api.census.gov/data/timeseries/eits/marts", params=params)
    try:
        payload = result.json()
    except json.JSONDecodeError:
        return _parse_json_or_error(candidate, result)
    return _json_probe_result(
        candidate,
        result,
        payload=payload,
        secret_alias=public_secret_summary(secret),
    )


def probe_bea(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    del sec_user_agent
    candidate = SOURCES["bea"]
    secret = load_secret_alias("bea")
    summary = public_secret_summary(secret)
    api_key = secret.values.get("api_key")
    if not api_key:
        return ProbeResult.skipped(candidate, "missing BEA api_key secret alias", secret_alias=summary)
    result = client.get(
        "https://apps.bea.gov/api/data/",
        params={
            "UserID": str(api_key),
            "method": "GETPARAMETERLIST",
            "DatasetName": "NIPA",
            "ResultFormat": "JSON",
        },
    )
    try:
        payload = sanitize_value(result.json())
    except json.JSONDecodeError:
        return _parse_json_or_error(candidate, result)
    return _json_probe_result(
        candidate,
        result,
        payload=payload,
        row_path=("BEAAPI", "Results", "Parameter"),
        secret_alias=summary,
    )


def probe_bls(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    del sec_user_agent
    candidate = SOURCES["bls"]
    secret = load_secret_alias("bls")
    payload: dict[str, Any] = {"seriesid": ["CUUR0000SA0"]}
    if secret.values.get("api_key"):
        payload["registrationkey"] = str(secret.values["api_key"])
    result = client.post_json(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        payload=payload,
    )
    try:
        response = result.json()
    except json.JSONDecodeError:
        return _parse_json_or_error(candidate, result)
    rows = sample_rows(response, row_path=("Results",), limit=1)
    series = response.get("Results", {}).get("series", []) if isinstance(response, dict) else []
    if series and isinstance(series[0], dict):
        rows = sample_rows(series[0], row_path=("data",), limit=2)
    return ProbeResult(
        source=candidate.source,
        status="ok" if result.status and 200 <= result.status < 300 else "failed",
        available=bool(result.status and 200 <= result.status < 300),
        data_kind_candidates=list(candidate.data_kind_candidates),
        access=candidate.access,
        docs_url=candidate.docs_url,
        endpoint=sanitize_url(result.url),
        http_status=result.status,
        response_shape_keys=shape_keys(response),
        sample_rows=rows,
        secret_alias=public_secret_summary(secret),
        error_type=result.error_type,
        error_message=result.error_message,
        notes=["CUUR0000SA0 is used as a tiny CPI response-shape smoke sample."],
    )


def probe_fred(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    del sec_user_agent
    candidate = SOURCES["fred"]
    secret = load_secret_alias("fred")
    summary = public_secret_summary(secret)
    api_key = secret.values.get("api_key")
    if not api_key:
        return ProbeResult.skipped(candidate, "missing FRED api_key secret alias", secret_alias=summary)
    result = client.get(
        "https://api.stlouisfed.org/fred/series/search",
        params={
            "api_key": str(api_key),
            "file_type": "json",
            "search_text": "monetary service index",
            "limit": "1",
        },
    )
    try:
        payload = sanitize_value(result.json())
    except json.JSONDecodeError:
        return _parse_json_or_error(candidate, result)
    return _json_probe_result(
        candidate,
        result,
        payload=payload,
        row_path=("seriess",),
        secret_alias=summary,
    )


def probe_alpaca(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    del sec_user_agent
    candidate = SOURCES["alpaca"]
    secret = load_secret_alias("alpaca")
    summary = public_secret_summary(secret)
    api_key = secret.values.get("api_key")
    secret_key = secret.values.get("secret_key")
    if not api_key or not secret_key:
        return ProbeResult.skipped(candidate, "missing Alpaca api_key/secret_key alias", secret_alias=summary)
    endpoint = str(secret.values.get("endpoint") or "https://data.alpaca.markets")
    result = client.get(
        endpoint.rstrip("/") + "/v2/stocks/AAPL/bars",
        params={
            "timeframe": "1Day",
            "start": "2024-01-02T00:00:00Z",
            "end": "2024-01-03T00:00:00Z",
            "limit": "1",
            "adjustment": "raw",
        },
        headers={"APCA-API-KEY-ID": str(api_key), "APCA-API-SECRET-KEY": str(secret_key)},
    )
    try:
        payload = result.json()
    except json.JSONDecodeError:
        return _parse_json_or_error(candidate, result)
    return _json_probe_result(
        candidate,
        result,
        payload=sanitize_value(payload),
        row_path=("bars",),
        secret_alias=summary,
    )


def probe_thetadata(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    del sec_user_agent
    candidate = SOURCES["thetadata"]
    secret = load_secret_alias("thetadata")
    result = client.get("http://127.0.0.1:25510/v2/list/roots/option")
    if result.status is None:
        return ProbeResult(
            source=candidate.source,
            status="skipped",
            available=False,
            data_kind_candidates=list(candidate.data_kind_candidates),
            access=candidate.access,
            docs_url=candidate.docs_url,
            endpoint=sanitize_url(result.url),
            http_status=result.status,
            secret_alias=public_secret_summary(secret),
            skipped_reason="Theta Terminal not reachable on 127.0.0.1:25510",
            error_type=result.error_type,
            error_message=result.error_message,
        )
    try:
        payload = result.json()
    except json.JSONDecodeError:
        return _parse_json_or_error(candidate, result)
    return _json_probe_result(
        candidate,
        result,
        payload=sanitize_value(payload),
        row_path=("response",),
        secret_alias=public_secret_summary(secret),
    )


def probe_okx(client: HttpClient, sec_user_agent: str) -> ProbeResult:
    del sec_user_agent
    candidate = SOURCES["okx"]
    secret = load_secret_alias("okx")
    result = client.get(
        "https://www.okx.com/api/v5/market/tickers",
        params={"instType": "SPOT"},
    )
    try:
        payload = result.json()
    except json.JSONDecodeError:
        return _parse_json_or_error(candidate, result)
    return _json_probe_result(
        candidate,
        result,
        payload=sanitize_value(payload),
        row_path=("data",),
        secret_alias=public_secret_summary(secret),
    )


PROBES: dict[str, ProbeFn] = {
    "us_treasury_fiscal_data": probe_us_treasury_fiscal_data,
    "sec_edgar": probe_sec_edgar,
    "fomc_calendar": probe_fomc_calendar,
    "census": probe_census,
    "bea": probe_bea,
    "bls": probe_bls,
    "fred": probe_fred,
    "alpaca": probe_alpaca,
    "thetadata": probe_thetadata,
    "okx": probe_okx,
}
