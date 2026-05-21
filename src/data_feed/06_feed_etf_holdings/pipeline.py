"""ETF issuer holdings interface feed.

The feed normalizes issuer-published holdings into a single snapshot row shape.
It is conservative by default: users provide an official source URL and
captured/source text, while issuer-specific live fetch adapters require an
accepted ETF-symbol-to-issuer mapping table.
"""

from __future__ import annotations

import csv
import html
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from http.cookiejar import CookieJar
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
from xml.etree import ElementTree

from feed_availability.sanitize import sanitize_value
from data_runtime.config import resolve_output_root
from data_runtime.io import write_receipt_bundle
from data_runtime.provider_policy import require_provider_execution_allowed

FEED = "06_feed_etf_holdings"
FIELDS = [
    "etf_symbol",
    "issuer_name",
    "as_of_date",
    "holding_symbol",
    "holding_name",
    "weight",
    "shares",
    "market_value",
    "cusip",
    "sedol",
    "asset_class",
    "sector_type",
    "source_url",
]

ISSUER_FETCH_PATTERNS = {
    "ishares": "official CSV ajax endpoint from iShares fund page",
    "blackrock": "official CSV ajax endpoint from iShares fund page",
    "state_street": "official SSGA XLSX holdings-daily-us-en-<ticker>.xlsx",
    "spdr": "official SSGA XLSX holdings-daily-us-en-<ticker>.xlsx",
    "sector_spdr": "official SSGA XLSX holdings-daily-us-en-<ticker>.xlsx",
    "global_x": "official assets.globalxetfs.com dated full-holdings CSV",
    "ark": "official assets.ark-funds.com fund-documents CSV",
    "first_trust": "official ftportfolios.com holdings HTML table",
    "invesco": "official dng-api.invesco.com holdings JSON endpoint",
    "us_global": "official usglobaletfs.com fund-page holdings table",
    "vanguard": "official JS-rendered Vanguard profile holdings table",
    "vaneck": "official vaneck.com holdings XLSX download; may need browser/session headers",
}


@dataclass(frozen=True)
class FeedContext:
    task_key: dict[str, Any]
    run_dir: Path
    cleaned_dir: Path
    saved_dir: Path
    receipt_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepResult:
    status: str
    references: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeedPayload:
    kind: str
    text: str | bytes
    source_url: str


class EtfHoldingsError(ValueError):
    """Raised for invalid ETF holdings tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> FeedContext:
    if task_key.get("feed") != FEED:
        raise EtfHoldingsError(f"task_key.feed must be {FEED}")
    output_root = resolve_output_root(task_key, default_task_id=f"{FEED}_task")
    run_dir = output_root / "runs" / run_id
    return FeedContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _required(params: Mapping[str, Any], key: str) -> str:
    value = str(params.get(key) or "").strip()
    if not value:
        raise EtfHoldingsError(f"params.{key} is required")
    return value


def _etf_symbol_param(params: Mapping[str, Any]) -> str:
    value = str(params.get("etf_symbol") or params.get("etf_ticker") or "").strip().upper()
    if not value:
        raise EtfHoldingsError("params.etf_symbol is required")
    return value


def _issuer_key(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_")


def fetch(context: FeedContext) -> tuple[StepResult, FeedPayload]:
    params = dict(context.task_key.get("params") or {})
    etf_symbol = _etf_symbol_param(params)
    issuer = _issuer_key(str(params.get("issuer") or _required(params, "issuer_name")))
    source_url = str(params.get("source_url") or "")
    payload: FeedPayload | None = None
    for kind in ("csv", "html", "json", "xlsx"):
        if params.get(kind + "_path"):
            path = Path(str(params[kind + "_path"]))
            text: str | bytes = path.read_bytes() if kind == "xlsx" else path.read_text(encoding="utf-8")
            payload = FeedPayload(kind, text, source_url)
            break
        if params.get(kind + "_text"):
            payload = FeedPayload(kind, str(params[kind + "_text"]), source_url)
            break
        if params.get(kind):
            payload = FeedPayload(kind, str(params[kind]), source_url)
            break
    if payload is None:
        source_url = source_url or _default_source_url(etf_symbol, issuer, params)
        if source_url:
            require_provider_execution_allowed(
                context.task_key,
                provider="etf_issuer_holdings",
                endpoint_family="holdings_file",
                requested_symbols=1,
                requested_requests=2 if "vaneck.com" in source_url.lower() else 1,
            )
            payload = _fetch_source_url(source_url)
    if payload is None:
        raise EtfHoldingsError("provide one of params.csv_path/csv_text/html_path/html/json_path/json_text/xlsx_path or params.source_url")
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "feed": FEED,
        "etf_symbol": etf_symbol,
        "issuer_name": issuer,
        "issuer_pattern": ISSUER_FETCH_PATTERNS.get(issuer, "issuer adapter requires reviewed mapping"),
        "source_url": source_url,
        "feed_payload_kind": payload.kind,
        "fetched_at_utc": _now_utc(),
        "raw_persistence": "not_persisted_by_default",
    }
    path = context.run_dir / "request_manifest.json"
    path.write_text(json.dumps(sanitize_value(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path)], {"feed_payloads": 1}, details=manifest), payload


def _default_source_url(etf_symbol: str, issuer: str, params: Mapping[str, Any]) -> str:
    as_of = str(params.get("as_of_date") or _now_utc()[:10])[:10].replace("-", "")
    if issuer in {"ishares", "blackrock", "blackrock_ishares", "blackrock_/_ishares"}:
        product_ids = {
            "IGV": "239771",
            "IYT": "239501",
        }
        product_id = str(params.get("blackrock_product_id") or product_ids.get(etf_symbol.upper()) or "").strip()
        if not product_id:
            return ""
        query = urlencode(
            {
                "appSubType": "ISHARES",
                "appType": "PRODUCT_PAGE",
                "component": "holdings.all",
                "locale": "en_US",
                "portfolioId": product_id,
                "targetSite": "us-ishares",
                "userType": "individual",
                "excludeContent": "true",
                "asOfDate": str(params.get("blackrock_as_of_date") or ""),
                "includeConfig": "true",
            }
        )
        return "https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v2/get-product-data?" + query
    if issuer in {"state_street", "spdr", "sector_spdr", "state_street_spdr", "state_street_/_spdr"}:
        return f"https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{etf_symbol.lower()}.xlsx"
    if issuer == "global_x":
        return f"https://assets.globalxetfs.com/funds/holdings/{etf_symbol.lower()}_full-holdings_{as_of}.csv"
    if issuer == "ark_invest":
        ark_urls = {
            "ARKF": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.csv",
            "ARKG": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS.csv",
            "ARKW": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS.csv",
            "ARKX": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS.csv",
        }
        return ark_urls.get(etf_symbol.upper(), "")
    if issuer == "first_trust":
        return f"https://www.ftportfolios.com/Retail/Etf/EtfHoldings.aspx?Ticker={etf_symbol.upper()}"
    if issuer == "vaneck":
        vaneck_urls = {
            "SMH": "https://www.vaneck.com/us/en/etf/equity/smh/holdings/download/xlsx/",
        }
        return vaneck_urls.get(etf_symbol.upper(), "")
    return ""


def _fetch_source_url(source_url: str) -> FeedPayload:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; OpenClaw ETF holdings research/1.0)", "Accept": "application/json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/html,*/*"}
    opener = None
    if "vaneck.com" in source_url.lower():
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        warmup = Request("https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/holdings/", headers=headers)
        opener.open(warmup, timeout=30).read(1024)
    request = Request(source_url, headers=headers)
    open_fn = opener.open if opener is not None else urlopen
    with open_fn(request, timeout=30) as response:
        content_type = str(response.headers.get("content-type") or "").lower()
        data = response.read()
    lower_url = source_url.lower()
    if lower_url.endswith(".xlsx") or "spreadsheetml" in content_type:
        return FeedPayload("xlsx", data, source_url)
    text = data.decode("utf-8-sig", errors="replace")
    if lower_url.endswith(".json") or "json" in content_type:
        return FeedPayload("json", text, source_url)
    if lower_url.endswith(".csv") or "csv" in content_type or "," in text.splitlines()[0]:
        return FeedPayload("csv", text, source_url)
    return FeedPayload("html", text, source_url)


def _canonical_key(key: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    aliases = {
        "ticker": "holding_symbol",
        "symbol": "holding_symbol",
        "holding_symbol": "holding_symbol",
        "identifier": "holding_symbol",
        "name": "holding_name",
        "holding": "holding_name",
        "holdings": "holding_name",
        "company": "holding_name",
        "security_name": "holding_name",
        "issue_name": "holding_name",
        "issuename": "holding_name",
        "weight": "weight",
        "holding_percent": "weight",
        "holdingpercent": "weight",
        "net_assets": "weight",
        "weight_%": "weight",
        "weight_percent": "weight",
        "%_of_net_assets": "weight",
        "of_net_assets": "weight",
        "%_of_fund": "weight",
        "weighting": "weight",
        "shares": "shares",
        "shares_held": "shares",
        "shares_quantity": "shares",
        "units_held": "shares",
        "unitsheld": "shares",
        "market_value": "market_value",
        "market_value_us": "market_value",
        "market_value_": "market_value",
        "market_value_$": "market_value",
        "cusip": "cusip",
        "sedol": "sedol",
        "asset_class": "asset_class",
        "assetclass": "asset_class",
        "classification": "sector_type",
        "sector": "sector_type",
        "sector_name": "sector_type",
        "sectorname": "sector_type",
        "sector_type": "sector_type",
        "date": "as_of_date",
        "as_of_date": "as_of_date",
    }
    return aliases.get(key, key)


def _clean_num(value: Any) -> str:
    text = str(value or "").strip().replace("$", "").replace(",", "").replace("%", "")
    return text


def _normalize_row(raw: Mapping[str, Any], *, etf_symbol: str, issuer: str, source_url: str, default_as_of: str) -> dict[str, str]:
    mapped = {_canonical_key(str(key)): str(value or "").strip() for key, value in raw.items()}
    return {
        "etf_symbol": etf_symbol,
        "issuer_name": issuer,
        "as_of_date": _date_iso(mapped.get("as_of_date") or default_as_of),
        "holding_symbol": mapped.get("holding_symbol", ""),
        "holding_name": mapped.get("holding_name", ""),
        "weight": _clean_num(mapped.get("weight")),
        "shares": _clean_num(mapped.get("shares")),
        "market_value": _clean_num(mapped.get("market_value")),
        "cusip": mapped.get("cusip", ""),
        "sedol": mapped.get("sedol", ""),
        "asset_class": mapped.get("asset_class", ""),
        "sector_type": mapped.get("sector_type", ""),
        "source_url": source_url,
    }


def _parse_csv(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if "ticker" in line.lower() and ("weight" in line.lower() or "market value" in line.lower() or "% of" in line.lower())), 0)
    return list(csv.DictReader(StringIO("\n".join(lines[start:]))))


def _parse_xlsx(payload: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
        sheet = workbook.find(".//main:sheet", ns)
        if sheet is None:
            return []
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = None
        for rel in rels:
            if rel.attrib.get("Id") == rel_id:
                target = rel.attrib.get("Target")
                break
        if not target:
            return []
        sheet_path = target.lstrip("/")
        if not sheet_path.startswith("xl/"):
            sheet_path = "xl/" + sheet_path
        rows = []
        sheet_xml = ElementTree.fromstring(archive.read(sheet_path))
        for row in sheet_xml.findall(".//main:sheetData/main:row", ns):
            values = []
            for cell in row.findall("main:c", ns):
                value = cell.find("main:v", ns)
                inline = cell.find("main:is/main:t", ns)
                raw = inline.text if inline is not None else value.text if value is not None else ""
                if cell.attrib.get("t") == "s" and str(raw).isdigit():
                    raw = shared_strings[int(raw)]
                values.append(str(raw or "").strip())
            if any(values):
                rows.append(values)
        default_as_of = ""
        for row in rows:
            joined = " ".join(row)
            match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", joined)
            if match:
                default_as_of = match.group(1)
                break
        header_i = next((i for i, row in enumerate(rows) if any(cell.lower() in {"ticker", "symbol"} for cell in row) and any("weight" in cell.lower() or "%" in cell for cell in row)), -1)
        if header_i < 0:
            return []
        headers = rows[header_i]
        parsed = []
        for row in rows[header_i + 1:]:
            if len(row) < 2:
                continue
            parsed_row = {header: row[idx] if idx < len(row) else "" for idx, header in enumerate(headers)}
            if default_as_of and not any(_canonical_key(header) == "as_of_date" for header in parsed_row):
                parsed_row["as_of_date"] = default_as_of
            parsed.append(parsed_row)
        return parsed


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []
    for item in root.findall("main:si", ns):
        strings.append("".join(text.text or "" for text in item.findall(".//main:t", ns)))
    return strings


def _clean_cell(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _date_iso(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text[:20], fmt).date().isoformat()
        except ValueError:
            continue
    return text[:10]


def _parse_html(text: str) -> list[dict[str, Any]]:
    rows = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, flags=re.I | re.S):
        rows.append([_clean_cell(cell) for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html, flags=re.I | re.S)])
    symbol_headers = {"ticker", "symbol", "identifier"}
    header_i = next((i for i, row in enumerate(rows) if any(cell.lower() in symbol_headers for cell in row) and any("weight" in cell.lower() or "%" in cell for cell in row)), -1)
    if header_i < 0:
        return []
    headers = rows[header_i]
    parsed = []
    for row in rows[header_i + 1:]:
        if len(row) < 2:
            continue
        parsed.append({header: row[idx] if idx < len(row) else "" for idx, header in enumerate(headers)})
    return parsed


def _iter_json_rows(value: Any) -> Iterable[Mapping[str, Any]]:
    yield from _iter_blackrock_holdings_rows(value)
    if isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                yield item
    elif isinstance(value, Mapping):
        for key in ("holdings", "data", "rows", "fundHoldings"):
            if key in value:
                yield from _iter_json_rows(value[key])


def _iter_blackrock_holdings_rows(value: Any) -> Iterable[Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return
    try:
        data_points = value["componentsByNameMap"]["holdings"]["containersByNameMap"]["all"]["dataPointsByNameMap"]
    except (KeyError, TypeError):
        return
    if not isinstance(data_points, Mapping):
        return
    tickers = _data_point_values(data_points.get("ticker"))
    if not tickers:
        return
    as_of = _date_iso(str(_data_point_scalar(data_points.get("asOfDate")) or ""))
    field_map = {
        "holding_symbol": tickers,
        "holding_name": _data_point_values(data_points.get("issueName")),
        "weight": _data_point_values(data_points.get("holdingPercent")),
        "shares": _data_point_values(data_points.get("unitsHeld")),
        "market_value": _data_point_values(data_points.get("marketValue")),
        "cusip": _data_point_values(data_points.get("cusip")),
        "sedol": _data_point_values(data_points.get("sedol")),
        "asset_class": _data_point_values(data_points.get("assetClass")),
        "sector_type": _data_point_values(data_points.get("sectorName")),
    }
    for idx, symbol in enumerate(tickers):
        row = {"as_of_date": as_of}
        for key, values in field_map.items():
            row[key] = values[idx] if idx < len(values) and values[idx] is not None else ""
        if str(symbol or "").strip():
            yield row


def _data_point_values(value: Any) -> list[Any]:
    if not isinstance(value, Mapping):
        return []
    values = value.get("value")
    if not isinstance(values, list):
        values = value.get("formattedValue")
    return list(values) if isinstance(values, list) else []


def _data_point_scalar(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return ""
    return value.get("value") or value.get("formattedValue") or ""


def clean(context: FeedContext, payload: FeedPayload) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    etf_symbol = _etf_symbol_param(params)
    issuer = _issuer_key(str(params.get("issuer") or _required(params, "issuer_name")))
    as_of_date = str(params.get("as_of_date") or "")
    if payload.kind == "csv":
        raw_rows = _parse_csv(str(payload.text))
    elif payload.kind == "html":
        raw_rows = _parse_html(str(payload.text))
    elif payload.kind == "json":
        raw_rows = list(_iter_json_rows(json.loads(str(payload.text))))
    elif payload.kind == "xlsx":
        if not isinstance(payload.text, (bytes, bytearray)):
            raise EtfHoldingsError("xlsx payload must be bytes")
        raw_rows = _parse_xlsx(bytes(payload.text))
    else:
        raise EtfHoldingsError(f"unsupported feed payload kind {payload.kind}")
    rows = [_normalize_row(row, etf_symbol=etf_symbol, issuer=issuer, source_url=payload.source_url, default_as_of=as_of_date) for row in raw_rows]
    rows = [row for row in rows if row["holding_symbol"] or row["holding_name"]]
    if not rows:
        raise EtfHoldingsError("ETF holdings feed produced zero parseable holding rows")
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    path = context.cleaned_dir / "etf_holding_snapshot.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_value(row), sort_keys=True) + "\n")
    schema = context.cleaned_dir / "schema.json"
    schema.write_text(json.dumps({"etf_holding_snapshot": FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path), str(schema)], {"etf_holding_snapshot": len(rows)}, details={"columns": FIELDS})


def save(context: FeedContext, clean_result: StepResult) -> StepResult:
    rows = [json.loads(line) for line in (context.cleaned_dir / "etf_holding_snapshot.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / "etf_holding_snapshot.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return StepResult("succeeded", [str(path)], dict(clean_result.row_counts), details={"format": "csv", "columns": FIELDS})


def write_receipt(context: FeedContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: Exception | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "feed": FEED, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": str(context.metadata["run_id"]), "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != entry["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "feed": FEED})
    write_receipt_bundle(context.receipt_path, context.run_dir, existing)
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": entry["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, payload = fetch(context)
        clean_result = clean(context, payload)
        save_result = save(context, clean_result)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except Exception as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
