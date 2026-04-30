"""Manager-facing 02 SecuritySelectionModel ETF holdings input source."""
from __future__ import annotations

import csv
import json
import re
from importlib import import_module
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

_holding_feed = import_module("data_feed.06_feed_etf_holdings.pipeline")
clean_holding_feed = _holding_feed.clean
fetch_holding_feed = _holding_feed.fetch
build_holding_context = _holding_feed.build_context
RAW_HOLDING_FIELDS = _holding_feed.FIELDS
from feed_availability.sanitize import sanitize_value
from storage.sql import PostgresSqlTableWriter, SqlTableWriter

SOURCE = "source_02_security_selection"
MODEL_ID = "security_selection_model"
OUTPUT_TABLE = "source_02_security_selection"
SQL_FIELDS = [
    "etf_symbol",
    "issuer_name",
    "universe_type",
    "exposure_type",
    "as_of_date",
    "available_time",
    "holding_symbol",
    "holding_name",
    "weight",
    "shares",
    "market_value",
    "sector_type",
]
KEY_COLUMNS = ["etf_symbol", "as_of_date", "holding_symbol"]
MARKET_REGIME_ETF_UNIVERSE_PATH = Path("/root/projects/trading-storage/main/shared/market_regime_etf_universe.csv")
HOLDINGS_UNIVERSE_TYPE = "sector_observation_etf"
EXCLUDED_ASSET_PATTERNS = re.compile(r"\b(cash|money market|treasury|bond|fixed income|future|futures|swap|option|warrant|fund|etf|preferred)\b", re.I)
NON_US_MARKER = re.compile(r"\b(adr|gdr|foreign|depositary|ltd|plc|s\.a\.|ag|nv|oyj|asa|spa|se|kk|co ltd|limited)\b", re.I)


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
    universe_rows: list[dict[str, str]]
    raw_rows: list[dict[str, str]]


@dataclass(frozen=True)
class CleanedPayload:
    rows: list[dict[str, Any]]


class SecuritySelectionInputsError(ValueError):
    """Raised for invalid SecuritySelectionModel input tasks."""


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_context(task_key: dict[str, Any], run_id: str) -> SourceContext:
    if task_key.get("source") != SOURCE:
        raise SecuritySelectionInputsError(f"task_key.source must be {SOURCE}")
    output_root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', SOURCE + '_task')}"))
    return SourceContext(task_key, output_root / "runs" / run_id, output_root / "completion_receipt.json", {"run_id": run_id, "started_at": _now_utc()})


def _required(params: Mapping[str, Any], key: str) -> str:
    value = str(params.get(key) or "").strip()
    if not value:
        raise SecuritySelectionInputsError(f"params.{key} is required")
    return value


def _read_universe(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [{str(k): str(v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]
    rows = [row for row in rows if row.get("symbol") and row.get("issuer_name")]
    rows = [row for row in rows if row.get("universe_type") == HOLDINGS_UNIVERSE_TYPE]
    if not rows:
        raise SecuritySelectionInputsError(f"market regime ETF universe produced zero {HOLDINGS_UNIVERSE_TYPE} rows: {path}")
    return rows


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path("/root/projects/trading-main") / path


def fetch(context: SourceContext) -> tuple[StepResult, SourcePayload]:
    params = dict(context.task_key.get("params") or {})
    start = _required(params, "start")
    end = _required(params, "end")
    universe_path = _resolve_path(str(params.get("market_regime_etf_universe_path") or params.get("market_etf_universe_path") or MARKET_REGIME_ETF_UNIVERSE_PATH))
    universe_rows = _read_universe(universe_path)
    selected = _selected_symbols(universe_rows, params.get("symbols"))
    feed_payloads = params.get("holding_feed_payloads") or {}
    if not isinstance(feed_payloads, Mapping):
        raise SecuritySelectionInputsError("params.holding_feed_payloads must map ETF symbol to feed payload params")

    raw_rows: list[dict[str, str]] = []
    evidence: list[dict[str, Any]] = []
    for row in universe_rows:
        symbol = row["symbol"].upper()
        if symbol not in selected:
            continue
        payload_params = dict(feed_payloads.get(symbol) or {})
        if not payload_params:
            raise SecuritySelectionInputsError(f"missing params.holding_feed_payloads.{symbol}")
        raw_rows.extend(_fetch_one_holding_feed(context, row, payload_params, start=start, end=end, evidence=evidence))

    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": SOURCE,
        "model_id": MODEL_ID,
        "start": start,
        "end": end,
        "market_regime_etf_universe_path": str(universe_path),
        "universe_type_filter": HOLDINGS_UNIVERSE_TYPE,
        "symbols": sorted(selected),
        "holding_feeds": evidence,
        "raw_persistence": "run-local feed evidence only; final output is SQL",
        "fetched_at_utc": _now_utc(),
    }
    path = context.run_dir / "request_manifest.json"
    path.write_text(json.dumps(sanitize_value(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult("succeeded", [str(path)], {"raw_etf_holding_rows": len(raw_rows)}, details=manifest), SourcePayload(universe_rows, raw_rows)


def _selected_symbols(universe_rows: list[dict[str, str]], value: Any) -> set[str]:
    symbols = {row["symbol"].upper() for row in universe_rows}
    if not value:
        return symbols
    requested = {str(item).strip().upper() for item in (value if isinstance(value, list) else str(value).split(",")) if str(item).strip()}
    selected = symbols & requested
    if not selected:
        raise SecuritySelectionInputsError("no ETF symbols selected")
    return selected


def _fetch_one_holding_feed(context: SourceContext, universe_row: Mapping[str, str], payload_params: Mapping[str, Any], *, start: str, end: str, evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    symbol = str(universe_row["symbol"]).upper()
    issuer = str(universe_row["issuer_name"])
    params = {**dict(payload_params), "etf_symbol": symbol, "issuer_name": issuer}
    params.setdefault("as_of_date", start[:10])
    feed_task = {"task_id": f"{context.task_key.get('task_id')}_{symbol}_holdings", "feed": "06_feed_etf_holdings", "params": params, "output_root": str(context.run_dir / "feed" / symbol)}
    feed_context = build_holding_context(feed_task, str(context.metadata["run_id"]))
    fetch_result, feed_payload = fetch_holding_feed(feed_context)
    clean_result = clean_holding_feed(feed_context, feed_payload)
    rows = [json.loads(line) for line in (feed_context.cleaned_dir / "etf_holding_snapshot.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    evidence.append({"etf_symbol": symbol, "issuer_name": issuer, "start": start, "end": end, "fetch": asdict(fetch_result), "clean": asdict(clean_result), "raw_rows": len(rows)})
    return [{field: str(row.get(field) or "") for field in RAW_HOLDING_FIELDS} for row in rows]


def clean(context: SourceContext, payload: SourcePayload) -> tuple[StepResult, CleanedPayload]:
    params = dict(context.task_key.get("params") or {})
    start = _required(params, "start")
    end = _required(params, "end")
    universe_by_symbol = {row["symbol"].upper(): row for row in payload.universe_rows}
    rows: list[dict[str, Any]] = []
    skipped = {"non_us_or_non_equity": 0, "outside_window": 0, "missing_symbol": 0}
    for raw in payload.raw_rows:
        symbol = str(raw.get("etf_symbol") or "").upper()
        holding_symbol = str(raw.get("holding_symbol") or "").strip().upper()
        as_of_date = str(raw.get("as_of_date") or "")[:10]
        if not holding_symbol:
            skipped["missing_symbol"] += 1
            continue
        if as_of_date and (as_of_date < start[:10] or as_of_date > end[:10]):
            skipped["outside_window"] += 1
            continue
        if not _is_us_equity_holding(raw):
            skipped["non_us_or_non_equity"] += 1
            continue
        universe = universe_by_symbol.get(symbol, {})
        rows.append({
            "etf_symbol": symbol,
            "issuer_name": str(universe.get("issuer_name") or raw.get("issuer_name") or ""),
            "universe_type": str(universe.get("universe_type") or ""),
            "exposure_type": str(universe.get("exposure_type") or ""),
            "as_of_date": as_of_date,
            "available_time": _available_time(params, raw, as_of_date),
            "holding_symbol": holding_symbol,
            "holding_name": str(raw.get("holding_name") or ""),
            "weight": _num(raw.get("weight")),
            "shares": _num(raw.get("shares")),
            "market_value": _num(raw.get("market_value")),
            "sector_type": str(raw.get("sector_type") or ""),
        })
    rows.sort(key=lambda row: (row["etf_symbol"], row["as_of_date"], row["holding_symbol"]))
    result = StepResult("succeeded", [], {OUTPUT_TABLE: len(rows)}, details={"columns": SQL_FIELDS, "table": OUTPUT_TABLE, "natural_key": KEY_COLUMNS, "skipped": skipped, "filter": "US-listed common equity holdings only"})
    return result, CleanedPayload(rows)


def _is_us_equity_holding(row: Mapping[str, str]) -> bool:
    symbol = str(row.get("holding_symbol") or "").strip().upper()
    name = str(row.get("holding_name") or "")
    asset_class = str(row.get("asset_class") or "")
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol):
        return False
    text = f"{asset_class} {name}"
    if EXCLUDED_ASSET_PATTERNS.search(text):
        return False
    if NON_US_MARKER.search(name):
        return False
    if asset_class and not re.search(r"equity|stock|common", asset_class, re.I):
        return False
    return True


def _available_time(params: Mapping[str, Any], row: Mapping[str, str], as_of_date: str) -> str:
    explicit = str(params.get("available_time") or row.get("available_time") or "").strip()
    if explicit:
        return explicit
    return f"{as_of_date}T09:30:00-04:00" if as_of_date else ""


def _num(value: Any) -> float | None:
    text = str(value or "").replace("$", "").replace(",", "").replace("%", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
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


def run(task_key: dict[str, Any], *, run_id: str, sql_writer: SqlTableWriter | None = None):
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, feed_payload = fetch(context)
        clean_result, cleaned_payload = clean(context, feed_payload)
        save_result = save(context, clean_result, cleaned_payload, sql_writer=sql_writer)
        return write_receipt(context, status="succeeded", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result)
    except BaseException as exc:
        return write_receipt(context, status="failed", fetch_result=fetch_result, clean_result=clean_result, save_result=save_result, error=exc)
