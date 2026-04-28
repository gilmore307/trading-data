"""Manager-facing MarketRegimeModel ETF bar bundle."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from trading_data.data_bundles.config import load_bundle_config
from trading_data.source_availability.http import HttpClient, HttpResult
from trading_data.source_availability.sanitize import sanitize_url
from trading_data.source_availability.secrets import load_secret_alias, public_secret_summary
from trading_data.storage.sql import PostgresSqlTableWriter, SqlTableWriter

BUNDLE = "01_market_regime_model_inputs"
MODEL_ID = "market_regime_model"
OUTPUT_NAME = "01_market_regime_model_inputs"
OUTPUT_TABLE = "market_regime_etf_bar"
ET = ZoneInfo("America/New_York")
FIELDS = ["symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume", "vwap", "trade_count"]
SQL_FIELDS = ["run_id", "task_id", *FIELDS, "created_at"]


@dataclass(frozen=True)
class BundleContext:
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
class SourcePayload:
    config: dict[str, Any]
    universe_rows: list[dict[str, str]]
    bars_by_symbol: dict[str, list[dict[str, Any]]]
    secret_alias: dict[str, Any] | None = None


@dataclass(frozen=True)
class CleanedPayload:
    rows: list[dict[str, Any]]


class MarketRegimeInputsError(ValueError):
    """Raised for invalid MarketRegimeModel input bundle tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(params: Mapping[str, Any], key: str) -> Any:
    value = params.get(key)
    if value in (None, "", []):
        raise MarketRegimeInputsError(f"params.{key} is required")
    return value


def _et_iso(value: Any) -> str:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(ET).isoformat()


def _normalize_timeframe(value: str) -> str:
    text = value.strip()
    mapping = {
        "1d": "1Day",
        "1day": "1Day",
        "day": "1Day",
        "daily": "1Day",
        "30m": "30Min",
        "30min": "30Min",
        "30minute": "30Min",
        "1m": "1Min",
        "1min": "1Min",
        "1minute": "1Min",
    }
    return mapping.get(text.lower(), text)


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise MarketRegimeInputsError(f"task_key.bundle must be {BUNDLE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _json_response(result: HttpResult) -> dict[str, Any]:
    if result.status is None:
        raise MarketRegimeInputsError(f"request failed before HTTP response: {result.error_type}: {result.error_message}")
    if result.status < 200 or result.status >= 300:
        raise MarketRegimeInputsError(f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}")
    payload = result.json()
    if not isinstance(payload, dict):
        raise MarketRegimeInputsError("Alpaca bars response was not a JSON object")
    return payload


def _fetch_paginated(client: HttpClient, url: str, params: dict[str, str], headers: dict[str, str], max_pages: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    page_token: str | None = None
    for _ in range(max_pages):
        page_params = dict(params)
        if page_token:
            page_params["page_token"] = page_token
        result = client.get(url, params=page_params, headers=headers)
        payload = _json_response(result)
        batch = payload.get("bars", [])
        if not isinstance(batch, list):
            raise MarketRegimeInputsError("Alpaca field 'bars' was not a list")
        rows.extend(batch)
        page_token = str(payload.get("next_page_token") or "") or None
        evidence.append({"endpoint": sanitize_url(result.url), "http_status": result.status, "row_count": len(batch), "has_next_page": bool(page_token)})
        if not page_token:
            break
    else:
        evidence.append({"warning": f"max_pages={max_pages} reached before pagination completed"})
    return rows, evidence


def _read_universe(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [{str(k): str(v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]
    rows = [row for row in rows if row.get("symbol") and row.get("bar_grain")]
    if not rows:
        raise MarketRegimeInputsError(f"market ETF universe produced zero rows: {path}")
    return rows


def fetch(context: BundleContext, *, client: HttpClient | None = None) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    config_path = str(params.get("config_path") or "") or None
    config = load_bundle_config(BUNDLE, config_path=config_path)
    start = str(_required(params, "start"))
    end = str(_required(params, "end"))
    universe_path = Path(str(config.get("market_etf_universe_path") or "storage/shared/market_etf_universe.csv"))
    if not universe_path.is_absolute():
        universe_path = Path("/root/projects/trading-main") / universe_path
    universe_rows = _read_universe(universe_path)
    symbols = sorted({row["symbol"].upper() for row in universe_rows})
    universe_by_symbol = {row["symbol"].upper(): row for row in universe_rows}
    if params.get("symbols"):
        requested = {str(item).strip().upper() for item in (params["symbols"] if isinstance(params["symbols"], list) else str(params["symbols"]).split(",")) if str(item).strip()}
        symbols = [symbol for symbol in symbols if symbol in requested]
    if not symbols:
        raise MarketRegimeInputsError("no market ETF symbols selected")

    client = client or HttpClient(timeout_seconds=int(params.get("timeout_seconds", config.get("timeout_seconds", 20))))
    secret = load_secret_alias(str(config.get("secret_alias") or "alpaca"))
    api_key = secret.values.get("api_key")
    secret_key = secret.values.get("secret_key")
    if not api_key or not secret_key:
        raise MarketRegimeInputsError("Alpaca requires api_key and secret_key")
    base_url = str(secret.values.get("data_endpoint") or config.get("data_endpoint") or "https://data.alpaca.markets").rstrip("/")
    headers = {"APCA-API-KEY-ID": str(api_key), "APCA-API-SECRET-KEY": str(secret_key)}
    limit = str(params.get("limit", config.get("limit", 1000)))
    max_pages = int(params.get("max_pages", config.get("max_pages", 10)))
    adjustment = str(params.get("adjustment", config.get("adjustment", "raw")))
    feed = str(params.get("feed", config.get("feed", ""))).strip()

    evidence: list[dict[str, Any]] = []
    bars_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for symbol in symbols:
        timeframe = _normalize_timeframe(str(universe_by_symbol[symbol].get("bar_grain") or config.get("default_timeframe") or "1Day"))
        request = {"timeframe": timeframe, "start": start, "end": end, "limit": limit, "adjustment": adjustment}
        if feed:
            request["feed"] = feed
        bars, symbol_evidence = _fetch_paginated(client, f"{base_url}/v2/stocks/{symbol}/bars", request, headers, max_pages)
        bars_by_symbol[symbol] = bars
        evidence.append({"symbol": symbol, "timeframe": timeframe, "pages": symbol_evidence, "raw_count": len(bars)})

    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(json.dumps({"bundle": BUNDLE, "model_id": MODEL_ID, "start": start, "end": end, "market_etf_universe_path": str(universe_path), "symbols": symbols, "bar_requests": evidence, "secret_alias": public_secret_summary(secret), "raw_persistence": "not_persisted_by_default", "fetched_at_utc": _now_utc()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest)], {"raw_bars_transient": sum(len(rows) for rows in bars_by_symbol.values())}, details={"symbols": symbols, "market_etf_universe_path": str(universe_path)}), SourcePayload(config, universe_rows, bars_by_symbol, public_secret_summary(secret))


def clean(context: BundleContext, payload: SourcePayload) -> tuple[StepResult, CleanedPayload]:
    universe_by_symbol = {row["symbol"].upper(): row for row in payload.universe_rows}
    rows: list[dict[str, Any]] = []
    for symbol in sorted(payload.bars_by_symbol):
        timeframe = _normalize_timeframe(str(universe_by_symbol[symbol].get("bar_grain") or payload.config.get("default_timeframe") or "1Day"))
        for bar in payload.bars_by_symbol[symbol]:
            rows.append({"symbol": symbol, "timeframe": timeframe, "timestamp": _et_iso(bar["t"]), "open": bar.get("o"), "high": bar.get("h"), "low": bar.get("l"), "close": bar.get("c"), "volume": bar.get("v"), "vwap": bar.get("vw"), "trade_count": bar.get("n")})
    rows.sort(key=lambda row: (str(row["timeframe"]), str(row["symbol"]), str(row["timestamp"])))
    result = StepResult("succeeded", [], {OUTPUT_TABLE: len(rows)}, details={"columns": SQL_FIELDS, "natural_key": ["run_id", "symbol", "timeframe", "timestamp"], "table": OUTPUT_TABLE})
    return result, CleanedPayload(rows)


def _build_sql_rows(context: BundleContext, payload: CleanedPayload) -> list[dict[str, Any]]:
    created_at = _now_utc()
    task_id = str(context.task_key.get("task_id") or "")
    run_id = str(context.metadata["run_id"])
    return [
        {
            "run_id": run_id,
            "task_id": task_id,
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "timestamp": row["timestamp"],
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "volume": row.get("volume"),
            "vwap": row.get("vwap"),
            "trade_count": row.get("trade_count"),
            "created_at": created_at,
        }
        for row in payload.rows
    ]


def save(context: BundleContext, clean_result: StepResult, payload: CleanedPayload, config: Mapping[str, Any], *, sql_writer: SqlTableWriter | None = None) -> StepResult:
    writer = sql_writer or PostgresSqlTableWriter.from_config(config)
    metadata = writer.write_rows(table=OUTPUT_TABLE, columns=SQL_FIELDS, rows=_build_sql_rows(context, payload), key_columns=["run_id", "symbol", "timeframe", "timestamp"])
    reference = str(metadata.get("qualified_table") or metadata.get("table") or OUTPUT_TABLE)
    return StepResult("succeeded", [reference], dict(clean_result.row_counts), details={"format": "sql_table", "table": OUTPUT_TABLE, "columns": SQL_FIELDS, "storage": metadata})


def write_receipt(context: BundleContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: BaseException | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "bundle": BUNDLE, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": str(context.metadata["run_id"]), "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != entry["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "bundle": BUNDLE})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": entry["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None, sql_writer: SqlTableWriter | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, source_payload = fetch(context, client=client)
        clean_result, cleaned_payload = clean(context, source_payload)
        save_result = save(context, clean_result, cleaned_payload, source_payload.config, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
