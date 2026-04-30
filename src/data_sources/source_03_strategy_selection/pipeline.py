"""Manager-facing 03 StrategySelectionModel bar/liquidity input source."""
from __future__ import annotations

import json
from importlib import import_module
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

aggregate_liquidity_bars = import_module("data_feed.02_feed_alpaca_liquidity.pipeline").aggregate_liquidity_bars
from feed_availability.http import HttpClient, HttpResult
from feed_availability.sanitize import sanitize_url, sanitize_value
from feed_availability.secrets import load_secret_alias, public_secret_summary
from storage.sql import PostgresSqlTableWriter, SqlTableWriter

SOURCE = "source_03_strategy_selection"
MODEL_ID = "strategy_selection_model"
OUTPUT_TABLE = "source_03_strategy_selection"
ET = ZoneInfo("America/New_York")
SQL_FIELDS = [
    "symbol",
    "timeframe",
    "timestamp",
    "bar_open",
    "bar_high",
    "bar_low",
    "bar_close",
    "bar_volume",
    "bar_vwap",
    "bar_trade_count",
    "dollar_volume",
    "quote_count",
    "avg_bid",
    "avg_ask",
    "avg_bid_size",
    "avg_ask_size",
    "avg_spread",
    "spread_bps",
    "last_bid",
    "last_ask",
]
KEY_COLUMNS = ["symbol", "timeframe", "timestamp"]
DEFAULT_SECRET_ALIAS = "alpaca"
DEFAULT_TIMEFRAME = "1Min"
DEFAULT_ADJUSTMENT = "raw"
DEFAULT_LIMIT = 1000
DEFAULT_MAX_PAGES = 10
DEFAULT_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class SourceContext:
    task_key: dict[str, Any]
    run_dir: Path
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
    timeframe: str
    bars_by_symbol: dict[str, list[dict[str, Any]]]
    trades_by_symbol: dict[str, list[dict[str, Any]]]
    quotes_by_symbol: dict[str, list[dict[str, Any]]]


@dataclass(frozen=True)
class CleanedPayload:
    rows: list[dict[str, Any]]


class StrategySelectionInputsError(ValueError):
    """Raised for invalid StrategySelectionModel input tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(params: Mapping[str, Any], key: str) -> Any:
    value = params.get(key)
    if value in (None, "", []):
        raise StrategySelectionInputsError(f"params.{key} is required")
    return value


def _et_iso(value: Any) -> str:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(ET).isoformat()


def build_context(task_key: dict[str, Any], run_id: str) -> SourceContext:
    if task_key.get("source") != SOURCE:
        raise StrategySelectionInputsError(f"task_key.source must be {SOURCE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', SOURCE + '_task')}"))
    return SourceContext(task_key, output_root / "runs" / run_id, output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _symbols(value: Any) -> list[str]:
    items = value if isinstance(value, list) else str(value).split(",")
    symbols = sorted({str(item).strip().upper() for item in items if str(item).strip()})
    if not symbols:
        raise StrategySelectionInputsError("params.symbols must contain at least one symbol")
    return symbols


def _json_response(result: HttpResult) -> dict[str, Any]:
    if result.status is None:
        raise StrategySelectionInputsError(f"request failed before HTTP response: {result.error_type}: {result.error_message}")
    if result.status < 200 or result.status >= 300:
        raise StrategySelectionInputsError(f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}")
    payload = result.json()
    if not isinstance(payload, dict):
        raise StrategySelectionInputsError("Alpaca response was not a JSON object")
    return payload


def _fetch_paginated(client: HttpClient, url: str, row_key: str, params: dict[str, str], headers: dict[str, str], max_pages: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    page_token: str | None = None
    for _ in range(max_pages):
        page_params = dict(params)
        if page_token:
            page_params["page_token"] = page_token
        result = client.get(url, params=page_params, headers=headers)
        payload = _json_response(result)
        batch = payload.get(row_key, [])
        if not isinstance(batch, list):
            raise StrategySelectionInputsError(f"Alpaca field {row_key!r} was not a list")
        rows.extend(batch)
        page_token = str(payload.get("next_page_token") or "") or None
        evidence.append({"endpoint": sanitize_url(result.url), "http_status": result.status, "row_count": len(batch), "has_next_page": bool(page_token)})
        if not page_token:
            break
    else:
        evidence.append({"warning": f"max_pages={max_pages} reached before pagination completed"})
    return rows, evidence


def fetch(context: SourceContext, *, client: HttpClient | None = None) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    start = str(_required(params, "start"))
    end = str(_required(params, "end"))
    symbols = _symbols(_required(params, "symbols"))
    timeframe = str(params.get("timeframe") or DEFAULT_TIMEFRAME)
    max_pages = int(params.get("max_pages", DEFAULT_MAX_PAGES))
    limit = str(params.get("limit", DEFAULT_LIMIT))
    feed = str(params.get("feed", "")).strip()
    adjustment = str(params.get("adjustment", DEFAULT_ADJUSTMENT))
    client = client or HttpClient(timeout_seconds=int(params.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)))
    secret = load_secret_alias(str(params.get("secret_alias") or DEFAULT_SECRET_ALIAS))
    api_key = secret.values.get("api_key")
    secret_key = secret.values.get("secret_key")
    if not api_key or not secret_key:
        raise StrategySelectionInputsError("Alpaca requires api_key and secret_key")
    base_url = str(secret.values.get("data_endpoint") or "https://data.alpaca.markets").rstrip("/")
    headers = {"APCA-API-KEY-ID": str(api_key), "APCA-API-SECRET-KEY": str(secret_key)}

    bars_by_symbol: dict[str, list[dict[str, Any]]] = {}
    trades_by_symbol: dict[str, list[dict[str, Any]]] = {}
    quotes_by_symbol: dict[str, list[dict[str, Any]]] = {}
    evidence: list[dict[str, Any]] = []
    common = {"start": start, "end": end, "limit": limit}
    if feed:
        common["feed"] = feed
    for symbol in symbols:
        bars_req = {**common, "timeframe": timeframe, "adjustment": adjustment}
        bars, bar_pages = _fetch_paginated(client, f"{base_url}/v2/stocks/{symbol}/bars", "bars", bars_req, headers, max_pages)
        trades, trade_pages = _fetch_paginated(client, f"{base_url}/v2/stocks/{symbol}/trades", "trades", common, headers, max_pages)
        quotes, quote_pages = _fetch_paginated(client, f"{base_url}/v2/stocks/{symbol}/quotes", "quotes", common, headers, max_pages)
        bars_by_symbol[symbol] = bars
        trades_by_symbol[symbol] = trades
        quotes_by_symbol[symbol] = quotes
        evidence.append({"symbol": symbol, "bars": bar_pages, "trades": trade_pages, "quotes": quote_pages, "raw_counts": {"bars": len(bars), "trades": len(trades), "quotes": len(quotes)}})

    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(json.dumps({"source": SOURCE, "model_id": MODEL_ID, "start": start, "end": end, "symbols": symbols, "timeframe": timeframe, "requests": evidence, "secret_alias": public_secret_summary(secret), "raw_persistence": "raw trades/quotes are transient; final output is interval bar/liquidity SQL", "fetched_at_utc": _now_utc()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest)], {"raw_bar_rows": sum(len(v) for v in bars_by_symbol.values()), "raw_trade_rows_transient": sum(len(v) for v in trades_by_symbol.values()), "raw_quote_rows_transient": sum(len(v) for v in quotes_by_symbol.values())}, details=sanitize_value({"symbols": symbols, "timeframe": timeframe})), SourcePayload(timeframe, bars_by_symbol, trades_by_symbol, quotes_by_symbol)


def clean(context: SourceContext, payload: SourcePayload) -> tuple[StepResult, CleanedPayload]:
    rows: list[dict[str, Any]] = []
    for symbol in sorted(payload.bars_by_symbol):
        liquidity_by_timestamp = {row["interval_start"]: row for row in aggregate_liquidity_bars(symbol, payload.trades_by_symbol.get(symbol, []), payload.quotes_by_symbol.get(symbol, []), payload.timeframe)}
        bar_timestamps: set[str] = set()
        for bar in payload.bars_by_symbol[symbol]:
            timestamp = _et_iso(bar["t"])
            bar_timestamps.add(timestamp)
            rows.append(_row(context, symbol, payload.timeframe, timestamp, bar, liquidity_by_timestamp.get(timestamp, {})))
        for timestamp, liquidity in liquidity_by_timestamp.items():
            if timestamp not in bar_timestamps:
                rows.append(_row(context, symbol, payload.timeframe, timestamp, {}, liquidity))
    rows.sort(key=lambda row: (row["symbol"], row["timeframe"], row["timestamp"]))
    result = StepResult("succeeded", [], {OUTPUT_TABLE: len(rows)}, details={"columns": SQL_FIELDS, "table": OUTPUT_TABLE, "natural_key": KEY_COLUMNS})
    return result, CleanedPayload(rows)


def _row(context: SourceContext, symbol: str, timeframe: str, timestamp: str, bar: Mapping[str, Any], liquidity: Mapping[str, Any]) -> dict[str, Any]:
    close = _num(bar.get("c", liquidity.get("bar_close", liquidity.get("close"))))
    volume = _num(bar.get("v", liquidity.get("bar_volume", liquidity.get("volume"))))
    avg_mid = _num(liquidity.get("avg_mid"))
    avg_spread = _num(liquidity.get("avg_spread"))
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "timestamp": timestamp,
        "bar_open": _num(bar.get("o", liquidity.get("bar_open", liquidity.get("open")))),
        "bar_high": _num(bar.get("h", liquidity.get("bar_high", liquidity.get("high")))),
        "bar_low": _num(bar.get("l", liquidity.get("bar_low", liquidity.get("low")))),
        "bar_close": close,
        "bar_volume": volume,
        "bar_vwap": _num(bar.get("vw", liquidity.get("bar_vwap", liquidity.get("vwap")))),
        "bar_trade_count": _int(bar.get("n", liquidity.get("bar_trade_count", liquidity.get("trade_count")))),
        "dollar_volume": close * volume if close is not None and volume is not None else None,
        "quote_count": _int(liquidity.get("quote_count")),
        "avg_bid": _num(liquidity.get("avg_bid")),
        "avg_ask": _num(liquidity.get("avg_ask")),
        "avg_bid_size": _num(liquidity.get("avg_bid_size")),
        "avg_ask_size": _num(liquidity.get("avg_ask_size")),
        "avg_spread": avg_spread,
        "spread_bps": (avg_spread / avg_mid * 10000) if avg_spread is not None and avg_mid else None,
        "last_bid": _num(liquidity.get("last_bid")),
        "last_ask": _num(liquidity.get("last_ask")),
    }


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def save(context: SourceContext, clean_result: StepResult, payload: CleanedPayload, *, sql_writer: SqlTableWriter | None = None) -> StepResult:
    writer = sql_writer or PostgresSqlTableWriter.from_config({})
    metadata = writer.write_rows(table=OUTPUT_TABLE, columns=SQL_FIELDS, rows=payload.rows, key_columns=KEY_COLUMNS)
    reference = str(metadata.get("qualified_table") or metadata.get("table") or OUTPUT_TABLE)
    return StepResult("succeeded", [reference], dict(clean_result.row_counts), details={"format": "sql_table", "table": OUTPUT_TABLE, "columns": SQL_FIELDS, "storage": metadata})


def write_receipt(context: SourceContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: BaseException | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "source": SOURCE, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {"run_id": str(context.metadata["run_id"]), "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": outputs, "row_counts": row_counts, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != entry["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "source": SOURCE})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": entry["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None, sql_writer: SqlTableWriter | None = None):
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, feed_payload = fetch(context, client=client)
        clean_result, cleaned_payload = clean(context, feed_payload)
        save_result = save(context, clean_result, cleaned_payload, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
