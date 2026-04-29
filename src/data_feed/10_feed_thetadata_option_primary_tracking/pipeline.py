"""ThetaData specified-contract option primary tracking feed.

Development-stage final output is ``option_bar.csv``. ThetaData 1-second
OHLC provider rows are fetched and normalized in memory; full raw provider
responses are not persisted by default.
"""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from feed_availability.http import HttpClient, HttpResult
from feed_availability.sanitize import sanitize_url, sanitize_value
from feed_availability.secrets import load_secret_alias, public_secret_summary

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
DEFAULT_REGISTRY_CSV = Path("/root/projects/trading-main/scripts/registry/current.csv")
FEED = "10_feed_thetadata_option_primary_tracking"
SUPPORTED_TIMEFRAMES = {
    "1Sec": 1,
    "1Min": 60,
    "5Min": 300,
    "15Min": 900,
    "30Min": 1800,
    "1Hour": 3600,
    "1Day": 86400,
}


@dataclass(frozen=True)
class FeedContext:
    task_key: dict[str, Any]
    run_dir: Path
    cleaned_dir: Path
    saved_dir: Path
    receipt_path: Path
    registry_csv: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepResult:
    status: str
    references: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


RETIRED_LOCAL_FIELD_PAYLOADS = {
    "fld_A7K3P2Q9": "id",
    "fld_ABN002": "evidence_window",
    "fld_ABN008": "source_references",
    "fld_EKIND001": "data_kind",
    "fld_EKIND002": "source_name",
    "fld_EVT001": "timeline_headline",
    "fld_EVT005": "symbols",
    "fld_EVT007": "event_link_url",
    "fld_EVT010": "event_id",
    "fld_EVT020": "summary",
    "fld_EVT037": "generated_at",
    "fld_OPD002": "contract",
    "fld_OPD003": "contract_symbol",
    "fld_OPD004": "triggered_indicators",
    "fld_OPD006": "window_start",
    "fld_OPD007": "window_end",
    "fld_OPD008": "triggering_trade",
    "fld_OPD009": "trade_side_type",
    "fld_OPD010": "quote_context",
    "fld_OPD011": "iv_context",
    "fld_OPD012": "iv_percentile_by_expiration",
    "fld_OPD014": "source_provider_name",
    "fld_OPD015": "raw_persistence",
    "fld_OPD016": "trade_timestamp",
    "fld_OPD018": "trade_size",
    "fld_OPD019": "trade_at_ask",
    "fld_OPD020": "opening_activity",
    "fld_OPD021": "iv_high_cross_section",
    "fld_OPD022": "statistics",
    "fld_OPD024": "trade_price",
    "fld_OPD028": "price_vs_ask",
    "fld_OPD030": "window_trade_count",
    "fld_OPD031": "window_volume",
    "fld_OPD032": "window_notional",
    "fld_OPD033": "first_seen_in_window",
    "fld_OPD037": "ask_touch_ratio",
    "fld_OPD038": "contract_prior_window_volume",
    "fld_OPD039": "volume_vs_prior_window_ratio",
    "fld_OPD040": "volume_percentile_20d_same_time",
    "fld_OPD041": "expiration_chain_contract_count",
    "fld_OPD042": "iv_rank_in_expiration",
    "fld_OPD043": "iv_zscore_by_expiration",
    "fld_OPD044": "standard_context",
    "fld_OPD045": "option_event_detail_standard_source_name",
    "fld_OPD046": "option_event_detail_standard_id",
    "fld_OPD048": "current_standard",
    "fld_OPD049": "max_price_vs_ask",
    "fld_OPD050": "min_ask_touch_ratio",
    "fld_OPD051": "min_window_volume",
    "fld_OPD052": "min_volume_percentile_20d_same_time",
    "fld_OPD053": "min_iv_percentile_by_expiration",
    "fld_OPD054": "min_iv_zscore_by_expiration",
    "fld_OPT001": "underlying",
    "fld_OPT002": "expiration",
    "fld_OPT003": "option_right_type",
    "fld_OPT004": "strike",
    "fld_OPT005": "snapshot_time",
    "fld_OPT006": "contract_count",
    "fld_OPT007": "contracts",
    "fld_OPT008": "quote",
    "fld_OPT009": "iv",
    "fld_OPT010": "greeks",
    "fld_OPT011": "underlying_context",
    "fld_OPT012": "derived",
    "fld_OPT013": "timestamp",
    "fld_OPT014": "timeframe",
    "fld_OPT015": "bar_open",
    "fld_OPT016": "bar_high",
    "fld_OPT017": "bar_low",
    "fld_OPT018": "bar_close",
    "fld_OPT019": "bar_volume",
    "fld_OPT020": "bar_trade_count",
    "fld_OPT021": "bar_vwap",
    "fld_OPT032": "bid",
    "fld_OPT033": "ask",
    "fld_OPT034": "mid",
    "fld_OPT035": "spread",
    "fld_OPT036": "spread_pct",
    "fld_OPT037": "bid_size",
    "fld_OPT038": "ask_size",
    "fld_OPT045": "implied_vol",
    "fld_OPT051": "delta",
    "fld_OPT052": "theta",
    "fld_OPT053": "vega",
    "fld_OPT054": "rho",
    "fld_OPT055": "epsilon",
    "fld_OPT056": "lambda",
    "fld_OPT057": "underlying_price",
    "fld_OPT058": "underlying_timestamp",
    "fld_OPT059": "days_to_expiration",
    "fld_OPT060": "bid_exchange",
    "fld_OPT061": "ask_exchange",
    "fld_OPT062": "bid_condition",
    "fld_OPT063": "ask_condition",
    "fld_OPT064": "iv_error",
    "fld_P8L2C4TY": "created_at",
    "fld_Q5F9M2NZ": "updated_at",
}

@dataclass(frozen=True)
class RegistryRef:
    id: str
    expected_kinds: tuple[str, ...]


@dataclass(frozen=True)
class FetchedOhlc:
    underlying: str
    expiration: str
    right: str
    strike: float
    timeframe: str
    start_date: date
    end_date: date
    source_rows: list[dict[str, Any]]
    request_evidence: dict[str, Any]
    secret_alias: dict[str, Any] | None


class ThetaDataOptionPrimaryTrackingError(ValueError):
    pass


class RegistryNames:
    """Resolve retained registry fields and retired local-output field names."""

    def __init__(self, registry_csv: Path = DEFAULT_REGISTRY_CSV) -> None:
        with registry_csv.open(newline="", encoding="utf-8") as handle:
            self._rows = {row["id"]: row for row in csv.DictReader(handle)}

    def payload(self, ref: RegistryRef) -> str:
        row = self._rows.get(ref.id)
        if row is None:
            try:
                return RETIRED_LOCAL_FIELD_PAYLOADS[ref.id]
            except KeyError as exc:
                raise ThetaDataOptionPrimaryTrackingError(f"registry id not found: {ref.id}") from exc
        if row["kind"] not in ref.expected_kinds:
            raise ThetaDataOptionPrimaryTrackingError(
                f"registry id {ref.id} expected kind in {ref.expected_kinds}, got kind={row['kind']}"
            )
        return row["payload"]


# Legacy local-output field ids. Current registry rows are used when present;
# retired preview-only ids fall back to code-local names and must not be re-registered.
def field(item_id: str) -> RegistryRef:
    return RegistryRef(item_id, ("field", "identity_field", "path_field", "temporal_field", "classification_field", "text_field", "parameter_field"))


def data_kind(item_id: str) -> RegistryRef:
    return RegistryRef(item_id, ("data_kind",))


DATA_KIND = field("fld_EKIND001")
SOURCE = field("fld_EKIND002")
OPTION_UNDERLYING = field("fld_OPT001")
OPTION_EXPIRATION = field("fld_OPT002")
OPTION_RIGHT_TYPE = field("fld_OPT003")
OPTION_STRIKE = field("fld_OPT004")
DATA_TIMESTAMP = field("fld_OPT013")
TIMEFRAME = field("fld_OPT014")
BAR_OPEN = field("fld_OPT015")
BAR_HIGH = field("fld_OPT016")
BAR_LOW = field("fld_OPT017")
BAR_CLOSE = field("fld_OPT018")
BAR_VOLUME = field("fld_OPT019")
BAR_TRADE_COUNT = field("fld_OPT020")
BAR_VWAP = field("fld_OPT021")
OPTION_BAR = data_kind("dki_OPBAR001")


CSV_FIELD_REFS = [
    OPTION_UNDERLYING,
    OPTION_EXPIRATION,
    OPTION_RIGHT_TYPE,
    OPTION_STRIKE,
    TIMEFRAME,
    DATA_TIMESTAMP,
    BAR_OPEN,
    BAR_HIGH,
    BAR_LOW,
    BAR_CLOSE,
    BAR_VOLUME,
    BAR_TRADE_COUNT,
    BAR_VWAP,
]


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise ThetaDataOptionPrimaryTrackingError(f"{FEED}.params.{key} is required")
    return value


def _parse_date(value: Any, key: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ThetaDataOptionPrimaryTrackingError(f"{FEED}.params.{key} must be YYYY-MM-DD") from exc


def _normalize_right(value: Any) -> str:
    right = str(value).upper()
    aliases = {"C": "CALL", "CALL": "CALL", "P": "PUT", "PUT": "PUT"}
    if right not in aliases:
        raise ThetaDataOptionPrimaryTrackingError(f"{FEED}.params.right must be CALL or PUT")
    return aliases[right]


def _normalize_strike(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ThetaDataOptionPrimaryTrackingError(f"{FEED}.params.strike must be numeric") from exc


def _thetadata_strike(value: float) -> str:
    return f"{value:.3f}"


def _parse_thetadata_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET)


def _json_response(result: HttpResult) -> Any:
    if result.status is None:
        raise ThetaDataOptionPrimaryTrackingError(
            f"request failed before HTTP response: {result.error_type}: {result.error_message}"
        )
    if result.status < 200 or result.status >= 300:
        raise ThetaDataOptionPrimaryTrackingError(
            f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}"
        )
    try:
        return result.json()
    except json.JSONDecodeError as exc:
        raise ThetaDataOptionPrimaryTrackingError("ThetaData response was not JSON") from exc


def _response_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("response"), list):
        raise ThetaDataOptionPrimaryTrackingError("ThetaData option OHLC response was not a list")
    rows = payload["response"]
    if not all(isinstance(row, dict) for row in rows):
        raise ThetaDataOptionPrimaryTrackingError("ThetaData option OHLC rows were not objects")
    return rows


def build_context(task_key: dict[str, Any], run_id: str) -> FeedContext:
    if task_key.get("feed") != FEED:
        raise ThetaDataOptionPrimaryTrackingError(f"task_key.feed must be {FEED}")
    root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', FEED + '_task')}"))
    run_dir = root / "runs" / run_id
    registry_csv = Path(str((task_key.get("params") or {}).get("registry_csv") or DEFAULT_REGISTRY_CSV))
    return FeedContext(
        task_key=task_key,
        run_dir=run_dir,
        cleaned_dir=run_dir / "cleaned",
        saved_dir=run_dir / "saved",
        receipt_path=root / "completion_receipt.json",
        registry_csv=registry_csv,
        metadata={"run_id": run_id, "started_at": _now_utc()},
    )


def fetch(context: FeedContext, *, client: HttpClient | None = None) -> tuple[StepResult, FetchedOhlc]:
    params = dict(context.task_key.get("params") or {})
    underlying = str(_required(params, "underlying")).upper()
    expiration = str(_required(params, "expiration"))
    right = _normalize_right(_required(params, "right"))
    strike = _normalize_strike(_required(params, "strike"))
    start_date = _parse_date(_required(params, "start_date"), "start_date")
    end_date = _parse_date(_required(params, "end_date"), "end_date")
    if end_date < start_date:
        raise ThetaDataOptionPrimaryTrackingError(f"{FEED}.params.end_date must be on or after start_date")
    timeframe = str(_required(params, "timeframe"))
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ThetaDataOptionPrimaryTrackingError(
            f"unsupported timeframe {timeframe!r}; supported={sorted(SUPPORTED_TIMEFRAMES)}"
        )

    base_url = str(params.get("thetadata_base_url") or "http://127.0.0.1:25503").rstrip("/")
    timeout = int(params.get("timeout_seconds", 30))
    client = client or HttpClient(timeout_seconds=timeout)

    secret_summary = None
    try:
        secret_summary = public_secret_summary(load_secret_alias("thetadata"))
    except Exception as exc:  # Local terminal may already be running; secret summary is evidence only.
        secret_summary = {"alias": "thetadata", "present": False, "error_type": type(exc).__name__}

    request_params = {
        "symbol": underlying,
        "expiration": expiration,
        "strike": _thetadata_strike(strike),
        "right": right.lower(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "format": "json",
    }
    result = client.get(
        f"{base_url}/v3/option/history/ohlc",
        params=request_params,
        headers={"Accept": "application/json"},
    )
    payload = _json_response(result)
    response_rows = _response_rows(payload)
    source_rows: list[dict[str, Any]] = []
    for response_row in response_rows:
        data = response_row.get("data")
        if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
            for item in data:
                if isinstance(item, Mapping):
                    source_rows.append(dict(item))

    context.run_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "endpoint": sanitize_url(result.url),
        "http_status": result.status,
        "response_contract_count": len(response_rows),
        "source_row_count": len(source_rows),
    }
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "feed": FEED,
                "underlying": underlying,
                "expiration": expiration,
                "right": right,
                "strike": strike,
                "timeframe": timeframe,
                "params": sanitize_value({**request_params, "aggregation_timeframe": timeframe}),
                "request": evidence,
                "secret_alias": secret_summary,
                "raw_persistence": "not_persisted_by_default",
                "fetched_at_utc": _now_utc(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return StepResult(
        "succeeded",
        [str(manifest)],
        {"option_ohlc_rows_transient": len(source_rows)},
        details={
            "underlying": underlying,
            "expiration": expiration,
            "right": right,
            "strike": strike,
            "timeframe": timeframe,
        },
    ), FetchedOhlc(
        underlying=underlying,
        expiration=expiration,
        right=right,
        strike=strike,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        source_rows=source_rows,
        request_evidence=evidence,
        secret_alias=secret_summary,
    )


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    number = _float(value)
    return int(number) if number is not None else 0


def _active_ohlc_row(row: Mapping[str, Any]) -> bool:
    return _int(row.get("volume")) > 0 or _int(row.get("count")) > 0


def _bucket_start_et(timestamp: datetime, timeframe: str) -> datetime:
    dt = timestamp.astimezone(ET)
    day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if timeframe == "1Day":
        return day_start
    seconds = SUPPORTED_TIMEFRAMES[timeframe]
    elapsed = int((dt - day_start).total_seconds())
    return day_start + timedelta(seconds=(elapsed // seconds) * seconds)


def _round_price(value: float | None) -> float | None:
    return round(value, 10) if value is not None else None


def _aggregate_rows(names: RegistryNames, fetched: FetchedOhlc) -> tuple[list[dict[str, Any]], int]:
    f = names.payload
    buckets: dict[str, dict[str, Any]] = {}
    active_count = 0
    sorted_rows = sorted(
        fetched.source_rows,
        key=lambda row: str(row.get("timestamp") or ""),
    )
    for source_row in sorted_rows:
        if not _active_ohlc_row(source_row):
            continue
        timestamp = _parse_thetadata_timestamp(source_row.get("timestamp"))
        if timestamp is None:
            continue
        active_count += 1
        bucket_timestamp = _bucket_start_et(timestamp, fetched.timeframe).isoformat()
        open_price = _float(source_row.get("open"))
        high_price = _float(source_row.get("high"))
        low_price = _float(source_row.get("low"))
        close_price = _float(source_row.get("close"))
        volume = _int(source_row.get("volume"))
        count = _int(source_row.get("count"))
        price_for_vwap = close_price if close_price not in (None, 0) else _float(source_row.get("vwap"))

        bucket = buckets.setdefault(
            bucket_timestamp,
            {
                f(OPTION_UNDERLYING): fetched.underlying,
                f(OPTION_EXPIRATION): fetched.expiration,
                f(OPTION_RIGHT_TYPE): fetched.right,
                f(OPTION_STRIKE): fetched.strike,
                f(TIMEFRAME): fetched.timeframe,
                f(DATA_TIMESTAMP): bucket_timestamp,
                f(BAR_OPEN): open_price,
                f(BAR_HIGH): high_price,
                f(BAR_LOW): low_price,
                f(BAR_CLOSE): close_price,
                f(BAR_VOLUME): 0,
                f(BAR_TRADE_COUNT): 0,
                "_notional": 0.0,
            },
        )
        if bucket[f(BAR_OPEN)] in (None, 0) and open_price not in (None, 0):
            bucket[f(BAR_OPEN)] = open_price
        if high_price not in (None, 0):
            current_high = bucket.get(f(BAR_HIGH))
            bucket[f(BAR_HIGH)] = high_price if current_high in (None, 0) else max(float(current_high), high_price)
        if low_price not in (None, 0):
            current_low = bucket.get(f(BAR_LOW))
            bucket[f(BAR_LOW)] = low_price if current_low in (None, 0) else min(float(current_low), low_price)
        if close_price not in (None, 0):
            bucket[f(BAR_CLOSE)] = close_price
        bucket[f(BAR_VOLUME)] = int(bucket[f(BAR_VOLUME)]) + volume
        bucket[f(BAR_TRADE_COUNT)] = int(bucket[f(BAR_TRADE_COUNT)]) + count
        if price_for_vwap is not None and volume:
            bucket["_notional"] = float(bucket["_notional"]) + price_for_vwap * volume

    output_rows: list[dict[str, Any]] = []
    for bucket_timestamp in sorted(buckets):
        row = buckets[bucket_timestamp]
        volume = int(row[f(BAR_VOLUME)])
        notional = float(row.pop("_notional"))
        row[f(BAR_VWAP)] = _round_price(notional / volume) if volume else None
        output_rows.append(row)
    return output_rows, active_count


def clean(context: FeedContext, fetched: FetchedOhlc) -> StepResult:
    names = RegistryNames(context.registry_csv)
    rows, active_count = _aggregate_rows(names, fetched)
    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = context.cleaned_dir / "option_bar.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    schema_path = context.cleaned_dir / "schema.json"
    schema_path.write_text(
        json.dumps({"option_bar": [names.payload(ref) for ref in CSV_FIELD_REFS]}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    warnings = []
    if not rows:
        warnings.append("ThetaData OHLC returned no nonzero-volume/count rows for the requested contract/range")
    return StepResult(
        "succeeded",
        [str(jsonl_path), str(schema_path)],
        {"option_bar": len(rows), "active_option_ohlc_rows_transient": active_count},
        warnings=warnings,
        details={
            "timezone": "America/New_York",
            "format": "jsonl",
            "zero_volume_placeholders_skipped": len(fetched.source_rows) - active_count,
            "vwap_method": "close_volume_weighted_from_1sec_ohlc",
        },
    )


def _read_cleaned_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save(context: FeedContext, clean_result: StepResult) -> StepResult:
    names = RegistryNames(context.registry_csv)
    fields = [names.payload(ref) for ref in CSV_FIELD_REFS]
    rows = _read_cleaned_rows(context.cleaned_dir / "option_bar.jsonl")
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / "option_bar.csv"
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, path)
    return StepResult(
        "succeeded",
        [str(path)],
        dict(clean_result.row_counts),
        warnings=list(clean_result.warnings),
        details={"format": "csv", "atomic_write": True},
    )


def write_receipt(
    context: FeedContext,
    *,
    status: str,
    fetch_result: StepResult | None = None,
    clean_result: StepResult | None = None,
    save_result: StepResult | None = None,
    error: BaseException | None = None,
) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "feed": FEED, "runs": []}
    if context.receipt_path.exists():
        try:
            existing = json.loads(context.receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    row_counts = (
        save_result.row_counts
        if save_result
        else clean_result.row_counts
        if clean_result
        else fetch_result.row_counts
        if fetch_result
        else {}
    )
    outputs = save_result.references if save_result else []
    warnings = [
        warning
        for result in (fetch_result, clean_result, save_result)
        if result is not None
        for warning in result.warnings
    ]
    entry = {
        "run_id": context.metadata["run_id"],
        "status": status,
        "started_at": context.metadata.get("started_at"),
        "completed_at": _now_utc(),
        "output_dir": str(context.run_dir),
        "outputs": outputs,
        "row_counts": row_counts,
        "warnings": warnings,
        "steps": {
            "fetch": asdict(fetch_result) if fetch_result else None,
            "clean": asdict(clean_result) if clean_result else None,
            "save": asdict(save_result) if save_result else None,
        },
        "error": None if error is None else {"type": type(error).__name__, "message": str(error)},
    }
    existing["runs"] = [
        run for run in existing.get("runs", []) if run.get("run_id") != context.metadata["run_id"]
    ] + [entry]
    existing.update({"task_id": context.task_key.get("task_id"), "feed": FEED})
    context.receipt_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return StepResult(
        status,
        [str(context.receipt_path), *outputs],
        row_counts,
        warnings=warnings,
        details={"run_id": context.metadata["run_id"], "error": entry["error"]},
    )


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, fetched = fetch(context, client=client)
        clean_result = clean(context, fetched)
        save_result = save(context, clean_result)
        return write_receipt(
            context,
            status="succeeded",
            fetch_result=fetch_result,
            clean_result=clean_result,
            save_result=save_result,
        )
    except BaseException as exc:
        return write_receipt(
            context,
            status="failed",
            fetch_result=fetch_result,
            clean_result=clean_result,
            save_result=save_result,
            error=exc,
        )
