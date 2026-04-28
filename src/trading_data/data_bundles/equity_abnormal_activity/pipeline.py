"""Derived equity abnormal activity event detector.

This bundle projects observable stock/ETF bars and optional liquidity bars into
compact event-style rows for EventOverlayModel. It does not acquire market data;
Alpaca source bundles own bar/liquidity acquisition.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from trading_data.data_bundles.config import load_bundle_config
from trading_data.source_availability.sanitize import sanitize_value

BUNDLE = "equity_abnormal_activity"
FIELDS = [
    "event_id",
    "symbol",
    "event_time",
    "effective_time",
    "event_type",
    "source_type",
    "title",
    "summary",
    "abnormal_activity_type",
    "evidence_window",
    "return_zscore",
    "volume_zscore",
    "relative_strength_zscore",
    "gap_pct",
    "liquidity_spread_zscore",
    "source_references",
    "taxonomy_context",
]


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
    bars: list[dict[str, str]]
    benchmark_bars: list[dict[str, str]]
    liquidity_rows: list[dict[str, str]]


class EquityAbnormalActivityError(ValueError):
    """Raised for invalid equity_abnormal_activity tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise EquityAbnormalActivityError(f"task_key.bundle must be {BUNDLE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    run_dir = output_root / "runs" / run_id
    return BundleContext(task_key, run_dir, run_dir / "cleaned", run_dir / "saved", output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _require(params: Mapping[str, Any], key: str) -> Any:
    value = params.get(key)
    if value in (None, "", []):
        raise EquityAbnormalActivityError(f"params.{key} is required")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{str(k): str(v or "") for k, v in row.items()} for row in csv.DictReader(handle)]


def fetch(context: BundleContext) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    bars_path = Path(str(_require(params, "bars_csv_path")))
    benchmark_path = Path(str(params["benchmark_bars_csv_path"])) if params.get("benchmark_bars_csv_path") else None
    liquidity_path = Path(str(params["liquidity_csv_path"])) if params.get("liquidity_csv_path") else None
    bars = _read_csv(bars_path)
    benchmark_bars = _read_csv(benchmark_path) if benchmark_path else []
    liquidity_rows = _read_csv(liquidity_path) if liquidity_path else []
    if not bars:
        raise EquityAbnormalActivityError("bars_csv_path produced zero rows")
    context.run_dir.mkdir(parents=True, exist_ok=True)
    config_path = str(params.get("config_path") or "") or None
    manifest = {
        "bundle": BUNDLE,
        "config": config_path or "bundle-local config.json",
        "bars_csv_path": str(bars_path),
        "benchmark_bars_csv_path": str(benchmark_path) if benchmark_path else None,
        "liquidity_csv_path": str(liquidity_path) if liquidity_path else None,
        "bar_rows": len(bars),
        "benchmark_bar_rows": len(benchmark_bars),
        "liquidity_rows": len(liquidity_rows),
        "raw_persistence": "not_applicable; derived from saved equity_bar/equity_liquidity_bar CSV inputs",
        "fetched_at_utc": _now_utc(),
    }
    path = context.run_dir / "request_manifest.json"
    path.write_text(json.dumps(sanitize_value(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path)], {"equity_bar_input": len(bars)}, details=manifest), SourcePayload(bars, benchmark_bars, liquidity_rows)


def _float(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        value_float = float(text)
    except ValueError:
        return None
    return value_float if math.isfinite(value_float) else None


def _zscore(value: float, history: list[float]) -> float | None:
    if len(history) < 2:
        return None
    mean = statistics.fmean(history)
    stdev = statistics.pstdev(history)
    if stdev == 0:
        return None
    return (value - mean) / stdev


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _returns_by_timestamp(rows: list[dict[str, str]]) -> dict[str, float]:
    out: dict[str, float] = {}
    prev_close: float | None = None
    for row in sorted(rows, key=lambda item: str(item.get("timestamp") or item.get("interval_start") or "")):
        close = _float(row.get("close"))
        timestamp = str(row.get("timestamp") or row.get("interval_start") or "")
        if close is not None and prev_close not in (None, 0) and timestamp:
            out[timestamp] = close / float(prev_close) - 1.0
        if close is not None:
            prev_close = close
    return out


def detect_events(*, bars: list[dict[str, str]], benchmark_bars: list[dict[str, str]] | None = None, liquidity_rows: list[dict[str, str]] | None = None, lookback_intervals: int = 20, min_abs_return_zscore: float = 3.0, min_volume_zscore: float = 3.0, min_abs_relative_strength_zscore: float = 3.0, min_abs_gap_pct: float = 0.04, min_liquidity_spread_zscore: float = 3.0, model_standard: str = "equity_abnormal_activity_v0") -> list[dict[str, str]]:
    sorted_bars = sorted(bars, key=lambda row: str(row.get("timestamp") or ""))
    symbol = str(sorted_bars[0].get("symbol") or "").upper() if sorted_bars else ""
    timeframe = str(sorted_bars[0].get("timeframe") or "") if sorted_bars else ""
    benchmark_returns = _returns_by_timestamp(benchmark_bars or [])
    liquidity_by_time = {str(row.get("interval_start") or ""): row for row in (liquidity_rows or [])}
    return_history: list[float] = []
    volume_history: list[float] = []
    relative_history: list[float] = []
    spread_history: list[float] = []
    prev_close: float | None = None
    events: list[dict[str, str]] = []
    for row in sorted_bars:
        ts = str(row.get("timestamp") or "")
        close = _float(row.get("close"))
        open_ = _float(row.get("open"))
        volume = _float(row.get("volume"))
        if not ts or close is None:
            continue
        ret = close / prev_close - 1.0 if prev_close not in (None, 0) else None
        gap = open_ / prev_close - 1.0 if open_ is not None and prev_close not in (None, 0) else None
        benchmark_ret = benchmark_returns.get(ts)
        relative = ret - benchmark_ret if ret is not None and benchmark_ret is not None else None
        liq = liquidity_by_time.get(ts, {})
        spread = _float(liq.get("avg_spread"))
        return_window = return_history[-lookback_intervals:] if len(return_history) >= lookback_intervals else []
        volume_window = volume_history[-lookback_intervals:] if len(volume_history) >= lookback_intervals else []
        relative_window = relative_history[-lookback_intervals:] if len(relative_history) >= lookback_intervals else []
        spread_window = spread_history[-lookback_intervals:] if len(spread_history) >= lookback_intervals else []
        return_z = _zscore(ret, return_window) if ret is not None else None
        volume_z = _zscore(volume, volume_window) if volume is not None else None
        relative_z = _zscore(relative, relative_window) if relative is not None else None
        spread_z = _zscore(spread, spread_window) if spread is not None else None
        activity: list[str] = []
        if return_z is not None and abs(return_z) >= min_abs_return_zscore:
            activity.append("return_zscore")
        if volume_z is not None and volume_z >= min_volume_zscore:
            activity.append("volume_spike")
        if relative_z is not None and abs(relative_z) >= min_abs_relative_strength_zscore:
            activity.append("sector_relative_move")
        if gap is not None and abs(gap) >= min_abs_gap_pct:
            activity.append("gap")
        if spread_z is not None and spread_z >= min_liquidity_spread_zscore:
            activity.append("liquidity_spread")
        if activity:
            event_id = f"eq_abn_{symbol}_{ts.replace('-', '').replace(':', '').replace('+', '').replace('T', '_')[:24]}"
            evidence_window = {"timeframe": timeframe, "event_time": ts, "lookback_intervals": lookback_intervals}
            refs = [f"alpaca_bars:{symbol}:{ts}"]
            if liq:
                refs.append(f"alpaca_liquidity:{symbol}:{ts}")
            if benchmark_ret is not None:
                refs.append(f"benchmark_return:{ts}")
            taxonomy = {"detector": model_standard, "benchmark_present": benchmark_ret is not None}
            events.append({
                "event_id": event_id,
                "symbol": symbol,
                "event_time": ts,
                "effective_time": ts,
                "event_type": "equity_abnormal_activity_event",
                "source_type": "alpaca_equity_market_data",
                "title": f"{symbol} abnormal equity activity",
                "summary": f"{symbol} triggered {', '.join(activity)} over {timeframe or 'input'} bars.",
                "abnormal_activity_type": ";".join(activity),
                "evidence_window": json.dumps(evidence_window, sort_keys=True),
                "return_zscore": _fmt(return_z),
                "volume_zscore": _fmt(volume_z),
                "relative_strength_zscore": _fmt(relative_z),
                "gap_pct": _fmt(gap),
                "liquidity_spread_zscore": _fmt(spread_z),
                "source_references": ";".join(refs),
                "taxonomy_context": json.dumps(taxonomy, sort_keys=True),
            })
        if ret is not None:
            return_history.append(ret)
        if volume is not None:
            volume_history.append(volume)
        if relative is not None:
            relative_history.append(relative)
        if spread is not None:
            spread_history.append(spread)
        prev_close = close
    return events


def clean(context: BundleContext, payload: SourcePayload) -> StepResult:
    params = dict(context.task_key.get("params") or {})
    config_path = str(params.get("config_path") or "") or None
    defaults = load_bundle_config(BUNDLE, config_path=config_path)
    effective = {**defaults, **params}
    rows = detect_events(
        bars=payload.bars,
        benchmark_bars=payload.benchmark_bars,
        liquidity_rows=payload.liquidity_rows,
        lookback_intervals=int(effective.get("lookback_intervals", 20)),
        min_abs_return_zscore=float(effective.get("min_abs_return_zscore", 3.0)),
        min_volume_zscore=float(effective.get("min_volume_zscore", 3.0)),
        min_abs_relative_strength_zscore=float(effective.get("min_abs_relative_strength_zscore", 3.0)),
        min_abs_gap_pct=float(effective.get("min_abs_gap_pct", 0.04)),
        min_liquidity_spread_zscore=float(effective.get("min_liquidity_spread_zscore", 3.0)),
        model_standard=str(effective.get("model_standard", "equity_abnormal_activity_v0")),
    )
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    output = context.cleaned_dir / "equity_abnormal_activity_event.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    schema = context.cleaned_dir / "schema.json"
    schema.write_text(json.dumps({"equity_abnormal_activity_event": FIELDS, "row_count": len(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(output), str(schema)], {"equity_abnormal_activity_event": len(rows)}, details={"columns": FIELDS})


def save(context: BundleContext, clean_result: StepResult) -> StepResult:
    rows = [json.loads(line) for line in (context.cleaned_dir / "equity_abnormal_activity_event.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / "equity_abnormal_activity_event.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return StepResult("succeeded", [str(path)], dict(clean_result.row_counts), details={"format": "csv", "columns": FIELDS})


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


def run(task_key: dict[str, Any], *, run_id: str) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, payload = fetch(context)
        clean_result = clean(context, payload)
        save_result = save(context, clean_result)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
