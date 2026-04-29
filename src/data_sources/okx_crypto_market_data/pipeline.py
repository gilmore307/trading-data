"""OKX crypto market-data acquisition and cleaning bundle."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from source_availability.http import HttpClient, HttpResult
from source_availability.sanitize import sanitize_url, sanitize_value

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
DEFAULT_TIMEOUT_SECONDS = 20
SUPPORTED_TIMEFRAMES = {"1Min": 60, "5Min": 300, "15Min": 900, "1Hour": 3600, "1Day": 86400}
OKX_BAR_MAP = {"1Min": "1m", "5Min": "5m", "15Min": "15m", "1Hour": "1H", "1Day": "1D"}

CRYPTO_BAR_FIELDS = ["symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume", "vwap", "trade_count"]
CRYPTO_TRADE_FIELDS = ["data_kind", "source", "symbol", "timestamp_utc", "timestamp", "trade_id", "side", "price", "size", "notional"]
CRYPTO_LIQUIDITY_FIELDS = ["symbol", "timeframe", "interval_start", "trade_count", "quote_count", "volume", "vwap", "open", "high", "low", "close", "avg_bid", "avg_ask", "avg_mid", "avg_spread", "last_bid", "last_ask", "last_mid", "vwap_minus_avg_mid"]


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
    timeframe: str
    candles: list[list[Any]]
    trades: list[dict[str, Any]]
    evidence: dict[str, Any]


class OkxCryptoMarketDataError(ValueError):
    """Raised for invalid OKX crypto market-data tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(mapping: dict[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise OkxCryptoMarketDataError(f"okx_crypto_market_data.params.{key} is required")
    return value


def _ms_to_utc(value: str | int | float) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


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
        raise OkxCryptoMarketDataError(f"request failed before HTTP response: {result.error_type}: {result.error_message}")
    if result.status < 200 or result.status >= 300:
        raise OkxCryptoMarketDataError(f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}")
    payload = result.json()
    if isinstance(payload, dict) and payload.get("code") not in (None, "0"):
        raise OkxCryptoMarketDataError(f"OKX returned code={payload.get('code')}: {payload.get('msg')}")
    return payload


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != "okx_crypto_market_data":
        raise OkxCryptoMarketDataError("task_key.bundle must be okx_crypto_market_data")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', 'okx_crypto_market_data_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def fetch(context: BundleContext, *, client: HttpClient | None = None) -> tuple[StepResult, FetchedPayload]:
    params = dict(context.task_key.get("params") or {})
    symbol = str(_required(params, "instId")).upper()
    timeframe = str(params.get("timeframe", "1Min"))
    if timeframe not in OKX_BAR_MAP:
        raise OkxCryptoMarketDataError(f"unsupported timeframe {timeframe!r}; supported={sorted(OKX_BAR_MAP)}")
    limit = str(params.get("limit", 100))
    client = client or HttpClient(timeout_seconds=int(params.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)))
    headers = {"User-Agent": "trading-data-okx-crypto-market-data/0.1", "Accept": "application/json"}
    base = str(params.get("base_url") or "https://www.okx.com").rstrip("/")
    candles_http = client.get(f"{base}/api/v5/market/candles", params={"instId": symbol, "bar": OKX_BAR_MAP[timeframe], "limit": limit}, headers=headers)
    trades_http = client.get(f"{base}/api/v5/market/trades", params={"instId": symbol, "limit": limit}, headers=headers)
    candles_payload = _json_response(candles_http)
    trades_payload = _json_response(trades_http)
    candles = candles_payload.get("data", []) if isinstance(candles_payload, dict) else []
    trades = trades_payload.get("data", []) if isinstance(trades_payload, dict) else []
    if not isinstance(candles, list) or not isinstance(trades, list):
        raise OkxCryptoMarketDataError("OKX data fields must be lists")
    evidence = {
        "symbol": symbol,
        "timeframe": timeframe,
        "params": sanitize_value({"instId": symbol, "timeframe": timeframe, "limit": limit}),
        "candles_endpoint": sanitize_url(candles_http.url),
        "trades_endpoint": sanitize_url(trades_http.url),
        "fetched_at_utc": _now_utc(),
        "quote_persistence": "quote/order-book derived features are nullable unless sampled snapshots are available",
    }
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(json.dumps({**evidence, "row_counts": {"raw_candles": len(candles), "raw_trades": len(trades)}}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(manifest)], {"raw_candles_transient": len(candles), "raw_trades_transient": len(trades)}, details={"symbol": symbol, "timeframe": timeframe}), FetchedPayload(symbol, timeframe, candles, trades, evidence)


def normalize_bars(symbol: str, candles: list[list[Any]], timeframe: str) -> list[dict[str, Any]]:
    rows = []
    for candle in candles:
        if len(candle) < 9:
            raise OkxCryptoMarketDataError(f"OKX candle row must have at least 9 fields: {candle!r}")
        ts = _ms_to_utc(candle[0])
        rows.append({
            "symbol": symbol, "timeframe": timeframe,
            "timestamp": _et_iso(ts),
            "open": float(candle[1]), "high": float(candle[2]), "low": float(candle[3]), "close": float(candle[4]),
            "volume": float(candle[5]), "vwap": None, "trade_count": None,
        })
    return sorted(rows, key=lambda row: row["timestamp"])


def normalize_trades(symbol: str, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        ts = _ms_to_utc(trade["ts"])
        price = float(trade["px"])
        size = float(trade["sz"])
        rows.append({
            "data_kind": "crypto_trade", "source": "okx", "symbol": symbol,
            "timestamp_utc": _utc_iso(ts), "timestamp": _et_iso(ts),
            "trade_id": str(trade.get("tradeId") or ""), "side": str(trade.get("side") or ""),
            "price": price, "size": size, "notional": round(price * size, 12),
        })
    return sorted(rows, key=lambda row: (row["timestamp_utc"], row["trade_id"]))


def aggregate_liquidity_bars(symbol: str, trades: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for trade in trades:
        ts = datetime.fromisoformat(str(trade["timestamp_utc"]))
        key = _bucket_start_et(ts, timeframe).isoformat()
        price = float(trade["price"])
        size = float(trade["size"])
        row = buckets.setdefault(key, {
            "symbol": symbol, "timeframe": timeframe,
            "interval_start": key, "trade_count": 0, "volume": 0.0, "trade_notional": 0.0,
            "open": price, "high": price, "low": price, "close": price,
            "quote_count": None, "avg_bid": None, "avg_ask": None, "avg_mid": None, "avg_spread": None,
            "last_bid": None, "last_ask": None, "last_mid": None, "vwap_minus_avg_mid": None,
        })
        row["trade_count"] += 1
        row["volume"] += size
        row["trade_notional"] += price * size
        row["high"] = max(row["high"], price)
        row["low"] = min(row["low"], price)
        row["close"] = price
    out = []
    for key in sorted(buckets):
        row = buckets[key]
        row["volume"] = round(row["volume"], 12)
        row["trade_notional"] = round(row["trade_notional"], 12)
        row["vwap"] = round(row["trade_notional"] / row["volume"], 10) if row["volume"] else None
        out.append(row)
    return out


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean(context: BundleContext, fetched: FetchedPayload) -> StepResult:
    bar_rows = normalize_bars(fetched.symbol, fetched.candles, fetched.timeframe)
    trade_rows = normalize_trades(fetched.symbol, fetched.trades)
    liquidity_rows = aggregate_liquidity_bars(fetched.symbol, trade_rows, fetched.timeframe)
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "crypto_bar": (bar_rows, CRYPTO_BAR_FIELDS),
        "crypto_liquidity_bar": (liquidity_rows, CRYPTO_LIQUIDITY_FIELDS),
    }
    transient_outputs = {"crypto_trade_transient": (trade_rows, CRYPTO_TRADE_FIELDS)}
    refs = []
    for name, (rows, _fields) in {**outputs, **transient_outputs}.items():
        path = context.cleaned_dir / f"{name}.jsonl"
        _write_jsonl(path, rows)
        refs.append(str(path))
    schema_path = context.cleaned_dir / "schema.json"
    schema_path.write_text(json.dumps({name: fields for name, (_rows, fields) in {**outputs, **transient_outputs}.items()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    refs.append(str(schema_path))
    row_counts = {name: len(rows) for name, (rows, _fields) in outputs.items()}
    row_counts["crypto_trade_transient"] = len(trade_rows)
    return StepResult("succeeded", refs, row_counts, details={"timezone": "America/New_York", "quote_features_available": False, "transient_inputs": ["crypto_trade"]})


def save(context: BundleContext) -> StepResult:
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "crypto_bar": CRYPTO_BAR_FIELDS,
        "crypto_liquidity_bar": CRYPTO_LIQUIDITY_FIELDS,
    }
    refs: list[str] = []
    counts: dict[str, int] = {}
    for name, fields in outputs.items():
        rows = [json.loads(line) for line in (context.cleaned_dir / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        csv_path = context.saved_dir / f"{name}.csv"
        _write_csv(csv_path, rows, fields)
        refs.append(str(csv_path))
        counts[name] = len(rows)
    return StepResult("succeeded", refs, counts, details={"format": "csv"})


def write_receipt(context: BundleContext, *, fetch_result: StepResult, clean_result: StepResult, save_result: StepResult, error: str | None = None) -> StepResult:
    existing = {"task_id": context.task_key.get("task_id"), "bundle": "okx_crypto_market_data", "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    run_entry = {
        "run_id": context.metadata["run_id"], "status": "failed" if error else "succeeded",
        "started_at": context.metadata["started_at"], "completed_at": _now_utc(), "output_dir": str(context.run_dir),
        "outputs": save_result.references, "row_counts": save_result.row_counts, "error": error,
        "steps": {"fetch": fetch_result.__dict__, "clean": clean_result.__dict__, "save": save_result.__dict__},
    }
    existing.update({"task_id": context.task_key.get("task_id"), "bundle": "okx_crypto_market_data"})
    existing.setdefault("runs", []).append(run_entry)
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(context.receipt_path)], {"runs_recorded": len(existing["runs"])})


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    empty = StepResult("skipped")
    try:
        fetch_result, fetched = fetch(context, client=client)
        clean_result = clean(context, fetched)
        save_result = save(context)
        write_receipt(context, fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
        return save_result
    except Exception as exc:
        error_result = StepResult("failed", warnings=[str(exc)])
        write_receipt(context, fetch_result=empty, clean_result=empty, save_result=error_result, error=str(exc))
        raise
