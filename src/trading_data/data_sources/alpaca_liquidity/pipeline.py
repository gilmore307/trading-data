"""Alpaca liquidity aggregate-only acquisition bundle."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from trading_data.source_availability.http import HttpClient, HttpResult
from trading_data.source_availability.sanitize import sanitize_url, sanitize_value
from trading_data.source_availability.secrets import load_secret_alias, public_secret_summary

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
DEFAULT_TIMEOUT_SECONDS = 20
SUPPORTED_TIMEFRAMES = {"1Min": 60, "5Min": 300, "15Min": 900, "1Hour": 3600, "1Day": 86400}


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
class FetchedPayload:
    symbol: str
    trades: list[dict[str, Any]]
    quotes: list[dict[str, Any]]
    request_evidence: dict[str, Any]
    secret_alias: dict[str, Any] | None = None


class AlpacaLiquidityError(ValueError):
    """Raised for invalid Alpaca liquidity aggregate tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(mapping: dict[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise AlpacaLiquidityError(f"alpaca_liquidity.params.{key} is required")
    return value


def _parse_ts(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text).astimezone(UTC)


def _et_iso(dt: datetime) -> str:
    return dt.astimezone(ET).isoformat()


def _bucket_start_et(dt_utc: datetime, timeframe: str) -> datetime:
    dt = dt_utc.astimezone(ET)
    if timeframe == "1Day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds = SUPPORTED_TIMEFRAMES[timeframe]
    day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = int((dt - day_start).total_seconds())
    return day_start + timedelta(seconds=(elapsed // seconds) * seconds)


def _json_response(result: HttpResult) -> Any:
    if result.status is None:
        raise AlpacaLiquidityError(f"request failed before HTTP response: {result.error_type}: {result.error_message}")
    if result.status < 200 or result.status >= 300:
        raise AlpacaLiquidityError(f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}")
    return result.json()


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != "alpaca_liquidity":
        raise AlpacaLiquidityError("task_key.bundle must be alpaca_liquidity")
    output_root = Path(str(task_key.get("output_root") or f"data/storage/{task_key.get('task_id', 'alpaca_liquidity_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def fetch(context: BundleContext, *, client: HttpClient | None = None) -> tuple[StepResult, FetchedPayload]:
    params = dict(context.task_key.get("params") or {})
    symbol = str(_required(params, "symbol")).upper()
    start = str(_required(params, "start"))
    end = str(_required(params, "end"))
    limit = str(params.get("limit", 1000))
    max_pages = int(params.get("max_pages", 10))
    feed = params.get("feed")
    client = client or HttpClient(timeout_seconds=int(params.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)))
    secret = load_secret_alias("alpaca")
    api_key = secret.values.get("api_key")
    secret_key = secret.values.get("secret_key")
    if not api_key or not secret_key:
        raise AlpacaLiquidityError("Alpaca requires api_key and secret_key in /root/secrets/alpaca.json or ALPACA_SECRET_ALIAS override")
    base = str(secret.values.get("data_endpoint") or "https://data.alpaca.markets").rstrip("/")
    headers = {"APCA-API-KEY-ID": str(api_key), "APCA-API-SECRET-KEY": str(secret_key)}
    common = {"start": start, "end": end, "limit": limit}
    if feed:
        common["feed"] = str(feed)
    trades, trade_evidence = _fetch_paginated(client, f"{base}/v2/stocks/{symbol}/trades", "trades", common, headers, max_pages)
    quotes, quote_evidence = _fetch_paginated(client, f"{base}/v2/stocks/{symbol}/quotes", "quotes", common, headers, max_pages)
    evidence = {
        "symbol": symbol,
        "trade_pages": trade_evidence,
        "quote_pages": quote_evidence,
        "params": sanitize_value({**common, "max_pages": max_pages}),
        "raw_persistence": "not_persisted_by_default; raw trades/quotes aggregate-only transient inputs",
        "fetched_at_utc": _now_utc(),
    }
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(json.dumps({**evidence, "secret_alias": public_secret_summary(secret), "raw_counts": {"trades": len(trades), "quotes": len(quotes)}}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest)], {"raw_trades_transient": len(trades), "raw_quotes_transient": len(quotes)}, details={"symbol": symbol}), FetchedPayload(symbol, trades, quotes, evidence, public_secret_summary(secret))


def _fetch_paginated(client: HttpClient, url: str, row_key: str, params: dict[str, str], headers: dict[str, str], max_pages: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    page_token: str | None = None
    for page in range(max_pages):
        page_params = dict(params)
        if page_token:
            page_params["page_token"] = page_token
        result = client.get(url, params=page_params, headers=headers)
        payload = _json_response(result)
        batch = payload.get(row_key, []) if isinstance(payload, dict) else []
        if not isinstance(batch, list):
            raise AlpacaLiquidityError(f"Alpaca response field {row_key!r} was not a list")
        rows.extend(batch)
        page_token = payload.get("next_page_token") if isinstance(payload, dict) else None
        evidence.append({"endpoint": sanitize_url(result.url), "http_status": result.status, "row_count": len(batch), "has_next_page": bool(page_token)})
        if not page_token:
            break
    else:
        evidence.append({"warning": f"max_pages={max_pages} reached before pagination completed"})
    return rows, evidence


def clean(context: BundleContext, fetched: FetchedPayload) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    timeframe = str(params.get("timeframe", "1Min"))
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise AlpacaLiquidityError(f"unsupported timeframe {timeframe!r}; supported={sorted(SUPPORTED_TIMEFRAMES)}")
    liquidity_rows = aggregate_liquidity_bars(fetched.symbol, fetched.trades, fetched.quotes, timeframe)
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    output = context.cleaned_dir / "equity_liquidity_bar.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for row in liquidity_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    schema_path = context.cleaned_dir / "schema.json"
    schema_path.write_text(json.dumps({"equity_liquidity_bar": sorted({key for row in liquidity_rows for key in row})}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(output), str(schema_path)], {"equity_liquidity_bar": len(liquidity_rows)}, details={"timeframe": timeframe, "timezone": "America/New_York"})


def aggregate_trades(symbol: str, trades: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for trade in trades:
        ts = _parse_ts(str(trade["t"]))
        bucket = _bucket_start_et(ts, timeframe)
        key = bucket.isoformat()
        price = float(trade.get("p") or 0)
        size = int(trade.get("s") or 0)
        row = buckets.setdefault(key, {"data_kind": "_transient_trade_interval", "symbol": symbol, "timeframe": timeframe, "interval_start_et": key, "trade_count": 0, "trade_volume": 0, "trade_notional": 0.0, "trade_open": price, "trade_high": price, "trade_low": price, "trade_close": price, "first_trade_ts_et": _et_iso(ts), "last_trade_ts_et": _et_iso(ts)})
        row["trade_count"] += 1
        row["trade_volume"] += size
        row["trade_notional"] += price * size
        row["trade_high"] = max(row["trade_high"], price)
        row["trade_low"] = min(row["trade_low"], price)
        row["trade_close"] = price
        row["last_trade_ts_et"] = _et_iso(ts)
    for row in buckets.values():
        row["trade_vwap"] = round(row["trade_notional"] / row["trade_volume"], 10) if row["trade_volume"] else None
        row["trade_notional"] = round(row["trade_notional"], 6)
    return [buckets[key] for key in sorted(buckets)]


def aggregate_quotes(symbol: str, quotes: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for quote in quotes:
        ts = _parse_ts(str(quote["t"]))
        bucket = _bucket_start_et(ts, timeframe)
        key = bucket.isoformat()
        bid = float(quote.get("bp") or 0)
        ask = float(quote.get("ap") or 0)
        bid_size = int(quote.get("bs") or 0)
        ask_size = int(quote.get("as") or 0)
        spread = ask - bid if bid and ask else None
        mid = (ask + bid) / 2 if bid and ask else None
        row = buckets.setdefault(key, {"data_kind": "_transient_quote_interval", "symbol": symbol, "timeframe": timeframe, "interval_start_et": key, "quote_count": 0, "sum_bid": 0.0, "sum_ask": 0.0, "sum_mid": 0.0, "sum_spread": 0.0, "spread_count": 0, "min_spread": None, "max_spread": None, "sum_bid_size": 0, "sum_ask_size": 0, "first_quote_ts_et": _et_iso(ts), "last_quote_ts_et": _et_iso(ts), "last_bid": bid, "last_ask": ask, "last_mid": mid})
        row["quote_count"] += 1
        row["sum_bid"] += bid
        row["sum_ask"] += ask
        row["sum_bid_size"] += bid_size
        row["sum_ask_size"] += ask_size
        if mid is not None:
            row["sum_mid"] += mid
        if spread is not None:
            row["sum_spread"] += spread
            row["spread_count"] += 1
            row["min_spread"] = spread if row["min_spread"] is None else min(row["min_spread"], spread)
            row["max_spread"] = spread if row["max_spread"] is None else max(row["max_spread"], spread)
        row["last_quote_ts_et"] = _et_iso(ts)
        row["last_bid"] = bid
        row["last_ask"] = ask
        row["last_mid"] = mid
    out = []
    for key in sorted(buckets):
        row = buckets[key]
        count = row.pop("quote_count")
        spread_count = row.pop("spread_count")
        sum_bid = row.pop("sum_bid"); sum_ask = row.pop("sum_ask"); sum_mid = row.pop("sum_mid"); sum_spread = row.pop("sum_spread")
        row.update({"quote_count": count, "avg_bid": round(sum_bid / count, 10) if count else None, "avg_ask": round(sum_ask / count, 10) if count else None, "avg_mid": round(sum_mid / count, 10) if count else None, "avg_spread": round(sum_spread / spread_count, 10) if spread_count else None, "avg_bid_size": round(row.pop("sum_bid_size") / count, 10) if count else None, "avg_ask_size": round(row.pop("sum_ask_size") / count, 10) if count else None})
        out.append(row)
    return out


def aggregate_liquidity_bars(symbol: str, trades: list[dict[str, Any]], quotes: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:
    # For this first implementation, liquidity is interval-level trade/quote
    # aggregation, not tick-level previous-quote matching. Tick-level matching can
    # be added later without changing the raw non-persistence rule.
    trade_by_bucket = {row["interval_start_et"]: row for row in aggregate_trades(symbol, trades, timeframe)}
    quote_by_bucket = {row["interval_start_et"]: row for row in aggregate_quotes(symbol, quotes, timeframe)}
    rows = []
    for key in sorted(set(trade_by_bucket) | set(quote_by_bucket)):
        t = trade_by_bucket.get(key, {})
        q = quote_by_bucket.get(key, {})
        trade_vwap = t.get("trade_vwap")
        avg_mid = q.get("avg_mid")
        rows.append({
            "data_kind": "equity_liquidity_bar",
            "symbol": symbol,
            "timeframe": timeframe,
            "interval_start_et": key,
            "trade_count": t.get("trade_count", 0),
            "quote_count": q.get("quote_count", 0),
            "trade_volume": t.get("trade_volume", 0),
            "trade_vwap": trade_vwap,
            "trade_open": t.get("trade_open"),
            "trade_high": t.get("trade_high"),
            "trade_low": t.get("trade_low"),
            "trade_close": t.get("trade_close"),
            "avg_bid": q.get("avg_bid"),
            "avg_ask": q.get("avg_ask"),
            "avg_mid": avg_mid,
            "avg_spread": q.get("avg_spread"),
            "min_spread": q.get("min_spread"),
            "max_spread": q.get("max_spread"),
            "avg_bid_size": q.get("avg_bid_size"),
            "avg_ask_size": q.get("avg_ask_size"),
            "last_bid": q.get("last_bid"),
            "last_ask": q.get("last_ask"),
            "last_mid": q.get("last_mid"),
            "last_trade_price": t.get("trade_close"),
            "vwap_minus_avg_mid": round(trade_vwap - avg_mid, 10) if isinstance(trade_vwap, (int, float)) and isinstance(avg_mid, (int, float)) else None,
        })
    return rows


def save(context: BundleContext, clean_result: StepResult) -> StepResult:
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    references = []
    for src in context.cleaned_dir.glob("*.jsonl"):
        rows = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines() if line.strip()]
        csv_path = context.saved_dir / (src.stem + ".csv")
        columns = sorted({key for row in rows for key in row.keys()})
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        references.append(str(csv_path))
    return StepResult("succeeded", references, dict(clean_result.row_counts), details={"format": "csv", "raw_persistence": "not_persisted_by_default"})


def write_receipt(context: BundleContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: BaseException | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {"task_id": context.task_key.get("task_id"), "bundle": "alpaca_liquidity", "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    entry = {"run_id": context.metadata["run_id"], "status": status, "started_at": context.metadata.get("started_at"), "completed_at": _now_utc(), "output_dir": str(context.run_dir), "outputs": save_result.references if save_result else [], "row_counts": save_result.row_counts if save_result else clean_result.row_counts if clean_result else {}, "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None}, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != context.metadata["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "bundle": "alpaca_liquidity"})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(status, [str(context.receipt_path), *entry["outputs"]], entry["row_counts"], details={"run_id": context.metadata["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, fetched = fetch(context, client=client)
        clean_result = clean(context, fetched)
        save_result = save(context, clean_result)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
