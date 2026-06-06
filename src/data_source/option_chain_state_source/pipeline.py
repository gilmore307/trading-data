"""Shared ThetaData option-chain source/cache acquisition.

The source writes one contract-level SQL row per visible option contract. It is
not model-facing output; Layer 3 and Layer 9 derive their own accepted surfaces
from these rows.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping

from data_runtime.config import resolve_output_root
from data_runtime.io import write_receipt_bundle
from feed_availability.http import HttpClient, RetryPolicy
from feed_availability.sanitize import sanitize_value
from storage.sql import PostgresSqlTableWriter, SqlTableWriter

_snapshot_feed = import_module("data_feed.09_feed_thetadata_option_selection_snapshot.pipeline")
build_snapshot_context = _snapshot_feed.build_context
clean_snapshot = _snapshot_feed.clean
fetch_snapshot = _snapshot_feed.fetch

SOURCE = "option_chain_state_source"
OUTPUT_TABLE = SOURCE
INPUT_FEED = "09_feed_thetadata_option_selection_snapshot"
DEFAULT_MAX_DTE = 365
DEFAULT_STRIKE_RANGE = 10
DEFAULT_OPTION_BUCKET_POLICY_REF = "TARGET_OPTION_CHAIN_STATE_REDUCTION_POLICY"
DEFAULT_PROVIDER_RETRY_ATTEMPTS = 3
DEFAULT_PROVIDER_RETRY_BACKOFF_SECONDS = 1.0

SQL_FIELDS = [
    "underlying",
    "snapshot_time",
    "option_symbol",
    "expiration",
    "option_right_type",
    "strike",
    "bid",
    "ask",
    "mid",
    "spread",
    "spread_pct",
    "bid_size",
    "ask_size",
    "bid_exchange",
    "ask_exchange",
    "bid_condition",
    "ask_condition",
    "implied_vol",
    "iv_error",
    "delta",
    "theta",
    "vega",
    "rho",
    "epsilon",
    "lambda",
    "underlying_price",
    "underlying_timestamp",
    "days_to_expiration",
    "bar_open",
    "bar_high",
    "bar_low",
    "bar_close",
    "bar_volume",
    "bar_trade_count",
    "bar_vwap",
    "trade_notional",
    "open_interest",
    "open_interest_change",
    "source_run_ref",
]
KEY_COLUMNS = ["underlying", "snapshot_time", "option_symbol"]


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
    snapshot: dict[str, Any]
    contract_count: int
    fetch_result: Any
    clean_result: Any


@dataclass(frozen=True)
class CleanedPayload:
    rows: list[dict[str, Any]]


class OptionChainStateSourceError(ValueError):
    """Raised for invalid shared option-chain source tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> SourceContext:
    if task_key.get("source") != SOURCE:
        raise OptionChainStateSourceError(f"task_key.source must be {SOURCE}")
    output_root = resolve_output_root(task_key, default_task_id=f"{SOURCE}_task")
    return SourceContext(task_key, output_root / "runs" / run_id, output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _feed_params(params: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(params),
        "max_dte": params.get("max_dte", DEFAULT_MAX_DTE),
        "strike_range": params.get("strike_range", DEFAULT_STRIKE_RANGE),
        "option_bucket_policy_ref": params.get("option_bucket_policy_ref", DEFAULT_OPTION_BUCKET_POLICY_REF),
    }


def fetch(context: SourceContext, *, client: HttpClient | None = None, client_is_fixture: bool = False) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    feed_params = _feed_params(params)
    feed_task = {
        "task_id": f"{context.task_key.get('task_id')}_option_chain_state_source",
        "feed": INPUT_FEED,
        "params": feed_params,
        "output_root": str(context.run_dir / "feed" / "option_chain_snapshot"),
        "manager_controls": context.task_key.get("manager_controls"),
    }
    feed_context = build_snapshot_context(feed_task, str(context.metadata["run_id"]))
    fetch_result, fetched = fetch_snapshot(feed_context, client=client, client_is_fixture=client_is_fixture)
    clean_result, snapshot = clean_snapshot(feed_context, fetched)
    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(
        json.dumps(
            sanitize_value(
                {
                    "source": SOURCE,
                    "input_feed": INPUT_FEED,
                    "params": {
                        "underlying": feed_params.get("underlying"),
                        "snapshot_time": feed_params.get("snapshot_time"),
                        "max_dte": feed_params.get("max_dte"),
                        "strike_range": feed_params.get("strike_range"),
                        "option_bucket_policy_ref": feed_params.get("option_bucket_policy_ref"),
                    },
                    "feed_fetch": asdict(fetch_result),
                    "feed_clean": asdict(clean_result),
                    "raw_persistence": "ThetaData raw responses are transient; final source/cache output is contract-level SQL rows",
                    "fetched_at_utc": _now_utc(),
                }
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return (
        StepResult(
            "succeeded",
            [str(manifest)],
            dict(clean_result.row_counts),
            details={"underlying": snapshot.get("underlying"), "snapshot_time": snapshot.get("snapshot_time")},
        ),
        SourcePayload(snapshot, int(clean_result.row_counts.get("option_chain_snapshot_contracts", 0)), fetch_result, clean_result),
    )


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


def option_symbol(underlying: str, expiration: str, right: str, strike: Any) -> str:
    code = "C" if str(right).upper().startswith("C") else "P" if str(right).upper().startswith("P") else str(right).upper()[:1]
    strike_value = _num(strike)
    strike_text = f"{strike_value:g}" if strike_value is not None else str(strike)
    return f"{underlying.upper()}_{expiration}_{code}_{strike_text}"


def _context(contract: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = contract.get(key) or {}
    return value if isinstance(value, Mapping) else {}


def flatten_contract(underlying: str, snapshot_time: str, contract: Mapping[str, Any], *, source_run_ref: str | None = None) -> dict[str, Any]:
    contract_snapshot_time = str(contract.get("snapshot_time") or snapshot_time)
    quote = _context(contract, "quote")
    iv = _context(contract, "iv")
    greeks = _context(contract, "greeks")
    derived = _context(contract, "derived")
    underlying_context = _context(contract, "underlying_context")
    trade_summary = _context(contract, "trade_summary")
    expiration = str(contract.get("expiration") or "")
    right = str(contract.get("option_right_type") or "")
    strike = _num(contract.get("strike"))
    bar_volume = _num(trade_summary.get("bar_volume"))
    bar_vwap = _num(trade_summary.get("bar_vwap"))
    return {
        "underlying": underlying,
        "snapshot_time": contract_snapshot_time,
        "option_symbol": option_symbol(underlying, expiration, right, strike if strike is not None else contract.get("strike")),
        "expiration": expiration,
        "option_right_type": right,
        "strike": strike,
        "bid": _num(quote.get("bid")),
        "ask": _num(quote.get("ask")),
        "mid": _num(quote.get("mid")),
        "spread": _num(quote.get("spread")),
        "spread_pct": _num(quote.get("spread_pct")),
        "bid_size": _num(quote.get("bid_size")),
        "ask_size": _num(quote.get("ask_size")),
        "bid_exchange": _int(quote.get("bid_exchange")),
        "ask_exchange": _int(quote.get("ask_exchange")),
        "bid_condition": _int(quote.get("bid_condition")),
        "ask_condition": _int(quote.get("ask_condition")),
        "implied_vol": _num(iv.get("implied_vol")),
        "iv_error": _num(iv.get("iv_error")),
        "delta": _num(greeks.get("delta")),
        "theta": _num(greeks.get("theta")),
        "vega": _num(greeks.get("vega")),
        "rho": _num(greeks.get("rho")),
        "epsilon": _num(greeks.get("epsilon")),
        "lambda": _num(greeks.get("lambda")),
        "underlying_price": _num(underlying_context.get("underlying_price")),
        "underlying_timestamp": underlying_context.get("underlying_timestamp"),
        "days_to_expiration": _int(derived.get("days_to_expiration")),
        "bar_open": _num(trade_summary.get("bar_open")),
        "bar_high": _num(trade_summary.get("bar_high")),
        "bar_low": _num(trade_summary.get("bar_low")),
        "bar_close": _num(trade_summary.get("bar_close")),
        "bar_volume": bar_volume,
        "bar_trade_count": _int(trade_summary.get("bar_trade_count")),
        "bar_vwap": bar_vwap,
        "trade_notional": None if bar_volume is None or bar_vwap is None else bar_volume * bar_vwap,
        "open_interest": None,
        "open_interest_change": None,
        "source_run_ref": source_run_ref,
    }


def clean(context: SourceContext, payload: SourcePayload) -> tuple[StepResult, CleanedPayload]:
    underlying = str(payload.snapshot.get("underlying") or "").upper()
    snapshot_time = str(payload.snapshot.get("snapshot_time") or "")
    contracts = payload.snapshot.get("contracts") or []
    if not isinstance(contracts, list):
        raise OptionChainStateSourceError("feed snapshot contracts must be a list")
    rows = [
        flatten_contract(underlying, snapshot_time, contract, source_run_ref=str(context.metadata.get("run_id") or ""))
        for contract in contracts
        if isinstance(contract, Mapping)
    ]
    rows.sort(key=lambda row: (row["snapshot_time"], row["expiration"], row["option_right_type"], row["strike"] if row["strike"] is not None else -1, row["option_symbol"]))
    result = StepResult("succeeded", [], {OUTPUT_TABLE: len(rows), "option_chain_snapshot_contracts": len(rows)}, details={"columns": SQL_FIELDS, "table": OUTPUT_TABLE, "natural_key": KEY_COLUMNS})
    return result, CleanedPayload(rows)


def save(context: SourceContext, clean_result: StepResult, payload: CleanedPayload, *, sql_writer: SqlTableWriter | None = None) -> StepResult:
    writer = sql_writer or PostgresSqlTableWriter.from_config({})
    metadata = writer.write_rows(table=OUTPUT_TABLE, columns=SQL_FIELDS, rows=payload.rows, key_columns=KEY_COLUMNS)
    reference = str(metadata.get("qualified_table") or metadata.get("table") or OUTPUT_TABLE)
    return StepResult("succeeded", [reference], dict(clean_result.row_counts), details={"format": "sql_table", "table": OUTPUT_TABLE, "columns": SQL_FIELDS, "storage": metadata})


def write_receipt(context: SourceContext, *, status: str, fetch_result: StepResult | None = None, clean_result: StepResult | None = None, save_result: StepResult | None = None, error: Exception | None = None) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "source": SOURCE, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = save_result.row_counts if save_result else clean_result.row_counts if clean_result else fetch_result.row_counts if fetch_result else {}
    outputs = save_result.references if save_result else []
    entry = {
        "run_id": str(context.metadata["run_id"]),
        "status": status,
        "started_at": context.metadata.get("started_at"),
        "completed_at": _now_utc(),
        "output_dir": str(context.run_dir),
        "outputs": outputs,
        "row_counts": row_counts,
        "steps": {"fetch": asdict(fetch_result) if fetch_result else None, "clean": asdict(clean_result) if clean_result else None, "save": asdict(save_result) if save_result else None},
        "error": None if error is None else {"type": type(error).__name__, "message": str(error)},
    }
    existing["runs"] = [run for run in existing.get("runs", []) if run.get("run_id") != entry["run_id"]] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "source": SOURCE})
    write_receipt_bundle(context.receipt_path, context.run_dir, existing)
    return StepResult(status, [str(context.receipt_path), *outputs], row_counts, details={"run_id": entry["run_id"], "error": entry["error"]})


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None, sql_writer: SqlTableWriter | None = None, client_is_fixture: bool = False):
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, source_payload = fetch(context, client=client, client_is_fixture=client_is_fixture)
        clean_result, cleaned_payload = clean(context, source_payload)
        save_result = save(context, clean_result, cleaned_payload, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except Exception as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)


def batch_http_client(task_key: Mapping[str, Any]) -> HttpClient:
    params = dict(task_key.get("params") or {})
    timeout = int(params.get("timeout_seconds", 30))
    retry_attempts = int(params.get("retry_attempts") or DEFAULT_PROVIDER_RETRY_ATTEMPTS)
    retry_backoff_seconds = float(params.get("retry_backoff_seconds") or DEFAULT_PROVIDER_RETRY_BACKOFF_SECONDS)
    return HttpClient(timeout_seconds=timeout, retry_policy=RetryPolicy(max_attempts=retry_attempts, backoff_seconds=retry_backoff_seconds))
