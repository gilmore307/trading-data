"""ThetaData option activity event timeline bundle.

Development-stage final outputs are ``option_activity_event.csv`` and one
``<event_id>.json`` detail artifact per emitted event. Provider trade/quote
rows are transient and are not persisted by default.
"""

from __future__ import annotations

import csv
import json
import os
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from trading_data.source_availability.http import HttpClient, HttpResult
from trading_data.source_availability.sanitize import sanitize_url, sanitize_value
from trading_data.source_availability.secrets import load_secret_alias, public_secret_summary

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
DEFAULT_REGISTRY_CSV = Path("/root/projects/trading-main/registry/current.csv")
BUNDLE = "thetadata_option_event_timeline"
SUPPORTED_TIMEFRAMES = {
    "1Min": 60,
    "5Min": 300,
    "15Min": 900,
    "30Min": 1800,
    "1Hour": 3600,
    "1Day": 86400,
}
ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass(frozen=True)
class BundleContext:
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


@dataclass(frozen=True)
class RegistryRef:
    id: str
    expected_kinds: tuple[str, ...]


@dataclass(frozen=True)
class FetchedTradeQuote:
    underlying: str
    expiration: str
    right: str
    strike: float
    timeframe: str
    start_date: date
    end_date: date
    rows: list[dict[str, Any]]
    current_standard: dict[str, Any]
    standard_context: dict[str, Any]
    iv_context: dict[str, Any] | None
    request_evidence: dict[str, Any]
    secret_alias: dict[str, Any] | None
    max_events: int


class ThetaDataOptionEventTimelineError(ValueError):
    pass


class RegistryNames:
    """Resolve output field names and data-kind values by stable registry id."""

    def __init__(self, registry_csv: Path = DEFAULT_REGISTRY_CSV) -> None:
        with registry_csv.open(newline="", encoding="utf-8") as handle:
            self._rows = {row["id"]: row for row in csv.DictReader(handle)}

    def payload(self, ref: RegistryRef) -> str:
        row = self._rows.get(ref.id)
        if row is None:
            raise ThetaDataOptionEventTimelineError(f"registry id not found: {ref.id}")
        if row["kind"] not in ref.expected_kinds:
            raise ThetaDataOptionEventTimelineError(
                f"registry id {ref.id} expected kind in {ref.expected_kinds}, got kind={row['kind']}"
            )
        return row["payload"]


# Output field ids. Do not replace these with literal output field names; the
# bundle resolves current registry payloads when it materializes rows.
def field(item_id: str) -> RegistryRef:
    return RegistryRef(item_id, ("field", "identity_field", "temporal_field", "classification_field"))


def data_kind(item_id: str) -> RegistryRef:
    return RegistryRef(item_id, ("data_kind",))


DATA_KIND = field("fld_EKIND001")
OPTION_UNDERLYING = field("fld_OPT001")
OPTION_EXPIRATION = field("fld_OPT002")
OPTION_RIGHT_TYPE = field("fld_OPT003")
OPTION_STRIKE = field("fld_OPT004")
DATA_TIMESTAMP = field("fld_OPT013")
DATA_TIMEFRAME = field("fld_OPT014")
QUOTE_BID = field("fld_OPT032")
QUOTE_ASK = field("fld_OPT033")
QUOTE_MID = field("fld_OPT034")
QUOTE_SPREAD = field("fld_OPT035")
IMPLIED_VOL = field("fld_OPT045")

TIMELINE_ID = field("fld_A7K3P2Q9")
TIMELINE_HEADLINE = field("fld_EVT001")
TIMELINE_CREATED_AT = field("fld_P8L2C4TY")
TIMELINE_UPDATED_AT = field("fld_Q5F9M2NZ")
TIMELINE_SYMBOLS = field("fld_EVT005")
TIMELINE_SUMMARY = field("fld_EVT020")
TIMELINE_URL = field("fld_EVT007")

OPTION_EVENT_DETAIL_EVENT_ID = field("fld_EVT010")
OPTION_EVENT_DETAIL_CONTRACT = field("fld_OPD002")
OPTION_CONTRACT_SYMBOL = field("fld_OPD003")
OPTION_EVENT_DETAIL_TRIGGERED_INDICATORS = field("fld_OPD004")
OPTION_EVENT_DETAIL_EVIDENCE_WINDOW = field("fld_ABN002")
WINDOW_START = field("fld_OPD006")
WINDOW_END = field("fld_OPD007")
OPTION_EVENT_DETAIL_TRIGGERING_TRADE = field("fld_OPD008")
TRADE_SIDE_TYPE = field("fld_OPD009")
OPTION_EVENT_DETAIL_QUOTE_CONTEXT = field("fld_OPD010")
OPTION_EVENT_DETAIL_IV_CONTEXT = field("fld_OPD011")
IV_PERCENTILE_BY_EXPIRATION = field("fld_OPD012")
OPTION_EVENT_DETAIL_SOURCE_REFS = field("fld_ABN008")
OPTION_EVENT_DETAIL_PROVIDER = field("fld_OPD014")
OPTION_EVENT_DETAIL_RAW_PERSISTENCE = field("fld_OPD015")
TRADE_TIMESTAMP = field("fld_OPD016")
TRADE_SIZE = field("fld_OPD018")
OPTION_EVENT_TRIGGER_TRADE_AT_ASK = field("fld_OPD019")
OPTION_EVENT_TRIGGER_OPENING_ACTIVITY = field("fld_OPD020")
OPTION_EVENT_TRIGGER_IV_HIGH_CROSS_SECTION = field("fld_OPD021")
OPTION_EVENT_DETAIL_STATISTICS = field("fld_OPD022")
TRADE_PRICE = field("fld_OPD024")
OPTION_EVENT_DETAIL_PRICE_VS_ASK = field("fld_OPD028")
WINDOW_TRADE_COUNT = field("fld_OPD030")
WINDOW_VOLUME = field("fld_OPD031")
WINDOW_NOTIONAL = field("fld_OPD032")
FIRST_SEEN_IN_WINDOW = field("fld_OPD033")
OPTION_EVENT_DETAIL_ASK_TOUCH_RATIO = field("fld_OPD037")
CONTRACT_PRIOR_WINDOW_VOLUME = field("fld_OPD038")
VOLUME_VS_PRIOR_WINDOW_RATIO = field("fld_OPD039")
VOLUME_PERCENTILE_20D_SAME_TIME = field("fld_OPD040")
EXPIRATION_CHAIN_CONTRACT_COUNT = field("fld_OPD041")
IV_RANK_IN_EXPIRATION = field("fld_OPD042")
IV_ZSCORE_BY_EXPIRATION = field("fld_OPD043")
OPTION_EVENT_DETAIL_STANDARD_CONTEXT = field("fld_OPD044")
OPTION_EVENT_DETAIL_STANDARD_SOURCE = field("fld_OPD045")
OPTION_EVENT_DETAIL_STANDARD_ID = field("fld_OPD046")
GENERATED_AT = field("fld_EVT037")
OPTION_EVENT_DETAIL_CURRENT_STANDARD = field("fld_OPD048")
OPTION_EVENT_STANDARD_MAX_PRICE_VS_ASK = field("fld_OPD049")
OPTION_EVENT_STANDARD_MIN_ASK_TOUCH_RATIO = field("fld_OPD050")
OPTION_EVENT_STANDARD_MIN_WINDOW_VOLUME = field("fld_OPD051")
OPTION_EVENT_STANDARD_MIN_VOLUME_PERCENTILE_20D_SAME_TIME = field("fld_OPD052")
OPTION_EVENT_STANDARD_MIN_IV_PERCENTILE_BY_EXPIRATION = field("fld_OPD053")
OPTION_EVENT_STANDARD_MIN_IV_ZSCORE_BY_EXPIRATION = field("fld_OPD054")

OPTION_ACTIVITY_EVENT = data_kind("dki_OPEVENT1")
OPTION_ACTIVITY_EVENT_DETAIL = data_kind("dki_OPDET01")

CSV_FIELD_REFS = [
    TIMELINE_ID,
    TIMELINE_HEADLINE,
    TIMELINE_CREATED_AT,
    TIMELINE_UPDATED_AT,
    TIMELINE_SYMBOLS,
    TIMELINE_SUMMARY,
    TIMELINE_URL,
]


@dataclass(frozen=True)
class EventRecord:
    row: dict[str, Any]
    detail: dict[str, Any]


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_et() -> str:
    return datetime.now(ET).replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return prefix + "_" + "".join(secrets.choice(ID_ALPHABET) for _ in range(8))


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise ThetaDataOptionEventTimelineError(f"{BUNDLE}.params.{key} is required")
    return value


def _parse_date(value: Any, key: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ThetaDataOptionEventTimelineError(f"{BUNDLE}.params.{key} must be YYYY-MM-DD") from exc


def _normalize_right(value: Any) -> str:
    right = str(value).upper()
    aliases = {"C": "CALL", "CALL": "CALL", "P": "PUT", "PUT": "PUT"}
    if right not in aliases:
        raise ThetaDataOptionEventTimelineError(f"{BUNDLE}.params.right must be CALL or PUT")
    return aliases[right]


def _normalize_strike(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ThetaDataOptionEventTimelineError(f"{BUNDLE}.params.strike must be numeric") from exc


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


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(ET).isoformat() if value is not None else None


def _json_response(result: HttpResult) -> Any:
    if result.status is None:
        raise ThetaDataOptionEventTimelineError(
            f"request failed before HTTP response: {result.error_type}: {result.error_message}"
        )
    if result.status < 200 or result.status >= 300:
        raise ThetaDataOptionEventTimelineError(
            f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}"
        )
    try:
        return result.json()
    except json.JSONDecodeError as exc:
        raise ThetaDataOptionEventTimelineError("ThetaData response was not JSON") from exc


def _response_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("response"), list):
        raise ThetaDataOptionEventTimelineError("ThetaData trade_quote response was not a list")
    rows = payload["response"]
    if not all(isinstance(row, dict) for row in rows):
        raise ThetaDataOptionEventTimelineError("ThetaData trade_quote rows were not objects")
    return rows


def _current_standard(params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    standard = params.get("current_standard")
    if not isinstance(standard, Mapping):
        raise ThetaDataOptionEventTimelineError(f"{BUNDLE}.params.current_standard is required")
    indicators = {k: v for k, v in standard.items() if k != "standard_context" and isinstance(v, Mapping)}
    if not indicators:
        raise ThetaDataOptionEventTimelineError(f"{BUNDLE}.params.current_standard must include indicator standards")
    context = dict(standard.get("standard_context") if isinstance(standard.get("standard_context"), Mapping) else {})
    context.setdefault("standard_source", "task_key_current_standard")
    context.setdefault("standard_id", _new_id("opt_evt_std"))
    context.setdefault("generated_at", context.get("standard_generated_at") or _now_et())
    context.pop("standard_generated_at", None)
    return {key: dict(value) for key, value in indicators.items()}, context


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise ThetaDataOptionEventTimelineError(f"task_key.bundle must be {BUNDLE}")
    root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    run_dir = root / "runs" / run_id
    registry_csv = Path(str((task_key.get("params") or {}).get("registry_csv") or DEFAULT_REGISTRY_CSV))
    return BundleContext(
        task_key=task_key,
        run_dir=run_dir,
        cleaned_dir=run_dir / "cleaned",
        saved_dir=run_dir / "saved",
        receipt_path=root / "completion_receipt.json",
        registry_csv=registry_csv,
        metadata={"run_id": run_id, "started_at": _now_utc()},
    )


def fetch(context: BundleContext, *, client: HttpClient | None = None) -> tuple[StepResult, FetchedTradeQuote]:
    params = dict(context.task_key.get("params") or {})
    underlying = str(_required(params, "underlying")).upper()
    expiration = str(_required(params, "expiration"))
    right = _normalize_right(_required(params, "right"))
    strike = _normalize_strike(_required(params, "strike"))
    start_date = _parse_date(_required(params, "start_date"), "start_date")
    end_date = _parse_date(_required(params, "end_date"), "end_date")
    if end_date < start_date:
        raise ThetaDataOptionEventTimelineError(f"{BUNDLE}.params.end_date must be on or after start_date")
    timeframe = str(_required(params, "timeframe"))
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ThetaDataOptionEventTimelineError(
            f"unsupported timeframe {timeframe!r}; supported={sorted(SUPPORTED_TIMEFRAMES)}"
        )
    current_standard, standard_context = _current_standard(params)
    max_events = int(params.get("max_events", 100))
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
        f"{base_url}/v3/option/history/trade_quote",
        params=request_params,
        headers={"Accept": "application/json"},
    )
    payload = _json_response(result)
    response_rows = _response_rows(payload)
    rows: list[dict[str, Any]] = []
    for response_row in response_rows:
        data = response_row.get("data")
        if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
            for item in data:
                if isinstance(item, Mapping):
                    rows.append(dict(item))

    context.run_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "endpoint": sanitize_url(result.url),
        "http_status": result.status,
        "response_contract_count": len(response_rows),
        "source_row_count": len(rows),
    }
    manifest = context.run_dir / "request_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "bundle": BUNDLE,
                "underlying": underlying,
                "expiration": expiration,
                "right": right,
                "strike": strike,
                "timeframe": timeframe,
                "params": sanitize_value({**request_params, "timeframe": timeframe, "max_events": max_events}),
                "current_standard": sanitize_value(current_standard),
                "standard_context": sanitize_value(standard_context),
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
        {"option_trade_quote_rows_transient": len(rows)},
        details={
            "underlying": underlying,
            "expiration": expiration,
            "right": right,
            "strike": strike,
            "timeframe": timeframe,
        },
    ), FetchedTradeQuote(
        underlying=underlying,
        expiration=expiration,
        right=right,
        strike=strike,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        rows=rows,
        current_standard=current_standard,
        standard_context=standard_context,
        iv_context=dict(params["iv_context"]) if isinstance(params.get("iv_context"), Mapping) else None,
        request_evidence=evidence,
        secret_alias=secret_summary,
        max_events=max_events,
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


def _bucket_start_et(timestamp: datetime, timeframe: str) -> datetime:
    dt = timestamp.astimezone(ET)
    day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if timeframe == "1Day":
        return day_start
    seconds = SUPPORTED_TIMEFRAMES[timeframe]
    elapsed = int((dt - day_start).total_seconds())
    return day_start + timedelta(seconds=(elapsed // seconds) * seconds)


def _contract_symbol(underlying: str, expiration: str, strike: float, right: str) -> str:
    strike_text = str(int(strike)) if float(strike).is_integer() else str(strike)
    suffix = "C" if right == "CALL" else "P"
    return f"{underlying} {expiration} {strike_text}{suffix}"


def _quote_stats(row: Mapping[str, Any]) -> dict[str, float | None]:
    bid = _float(row.get("bid"))
    ask = _float(row.get("ask"))
    mid = (bid + ask) / 2 if bid is not None and ask is not None else None
    spread = ask - bid if bid is not None and ask is not None else None
    return {"bid": bid, "ask": ask, "mid": mid, "spread": spread}


def _price_vs_ask(row: Mapping[str, Any]) -> float | None:
    price = _float(row.get("price"))
    ask = _float(row.get("ask"))
    return price - ask if price is not None and ask is not None else None


def _ask_touch_ratio(row: Mapping[str, Any]) -> float | None:
    price = _float(row.get("price"))
    bid = _float(row.get("bid"))
    ask = _float(row.get("ask"))
    if price is None or bid is None or ask is None:
        return None
    if ask == bid:
        return 1.0 if price >= ask else 0.0
    return (price - bid) / (ask - bid)


def _trigger_trade_at_ask(row: Mapping[str, Any], standard: Mapping[str, Any]) -> bool:
    price_vs_ask = _price_vs_ask(row)
    ask_touch_ratio = _ask_touch_ratio(row)
    max_price_vs_ask = _float(standard.get("max_price_vs_ask"))
    min_ask_touch_ratio = _float(standard.get("min_ask_touch_ratio"))
    if price_vs_ask is None or ask_touch_ratio is None:
        return False
    if max_price_vs_ask is not None and price_vs_ask > max_price_vs_ask:
        return False
    if min_ask_touch_ratio is not None and ask_touch_ratio < min_ask_touch_ratio:
        return False
    return True


def _window_stats(rows: Sequence[Mapping[str, Any]], prior_window_volume: int) -> dict[str, Any]:
    volume = sum(_int(row.get("size")) for row in rows)
    notional = sum((_float(row.get("price")) or 0.0) * _int(row.get("size")) for row in rows)
    return {
        "window_trade_count": len(rows),
        "window_volume": volume,
        "window_notional": notional,
        "first_seen_in_window": prior_window_volume == 0,
        "contract_prior_window_volume": prior_window_volume,
        "volume_vs_prior_window_ratio": None if prior_window_volume == 0 else volume / prior_window_volume,
        "volume_percentile_20d_same_time": None,
    }


def _trigger_opening_activity(stats: Mapping[str, Any], standard: Mapping[str, Any]) -> bool:
    min_window_volume = _float(standard.get("min_window_volume"))
    if min_window_volume is not None and _int(stats.get("window_volume")) < min_window_volume:
        return False
    percentile_threshold = _float(standard.get("min_volume_percentile_20d_same_time"))
    percentile = _float(stats.get("volume_percentile_20d_same_time"))
    if percentile_threshold is not None and (percentile is None or percentile < percentile_threshold):
        return False
    return min_window_volume is not None or percentile_threshold is not None


def _trigger_iv_high(iv_context: Mapping[str, Any], standard: Mapping[str, Any]) -> bool:
    percentile_threshold = _float(standard.get("min_iv_percentile_by_expiration"))
    zscore_threshold = _float(standard.get("min_iv_zscore_by_expiration"))
    percentile = _float(iv_context.get("iv_percentile_by_expiration"))
    zscore = _float(iv_context.get("iv_zscore_by_expiration"))
    if percentile_threshold is not None and (percentile is None or percentile < percentile_threshold):
        return False
    if zscore_threshold is not None and (zscore is None or zscore < zscore_threshold):
        return False
    return percentile_threshold is not None or zscore_threshold is not None


def _standard_by_registry_names(names: RegistryNames, standard: Mapping[str, Any]) -> dict[str, Any]:
    f = names.payload
    mapping = {
        "max_price_vs_ask": f(OPTION_EVENT_STANDARD_MAX_PRICE_VS_ASK),
        "min_ask_touch_ratio": f(OPTION_EVENT_STANDARD_MIN_ASK_TOUCH_RATIO),
        "min_window_volume": f(OPTION_EVENT_STANDARD_MIN_WINDOW_VOLUME),
        "min_volume_percentile_20d_same_time": f(OPTION_EVENT_STANDARD_MIN_VOLUME_PERCENTILE_20D_SAME_TIME),
        "min_iv_percentile_by_expiration": f(OPTION_EVENT_STANDARD_MIN_IV_PERCENTILE_BY_EXPIRATION),
        "min_iv_zscore_by_expiration": f(OPTION_EVENT_STANDARD_MIN_IV_ZSCORE_BY_EXPIRATION),
    }
    return {mapping.get(key, key): value for key, value in standard.items()}


def _event_headline(contract_symbol: str, triggered: Sequence[str]) -> str:
    phrases = {
        "trade_at_ask": "ask-side activity",
        "opening_activity": "opening activity",
        "iv_high_cross_section": "elevated IV",
    }
    joined = " with ".join(phrases.get(item, item) for item in triggered)
    return f"{contract_symbol} draws {joined}"


def _build_event(
    names: RegistryNames,
    fetched: FetchedTradeQuote,
    window_start: datetime,
    window_rows: Sequence[dict[str, Any]],
    prior_window_volume: int,
) -> EventRecord | None:
    f = names.payload
    standards = fetched.current_standard
    trade_at_ask_key = f(OPTION_EVENT_TRIGGER_TRADE_AT_ASK)
    opening_key = f(OPTION_EVENT_TRIGGER_OPENING_ACTIVITY)
    iv_key = f(OPTION_EVENT_TRIGGER_IV_HIGH_CROSS_SECTION)
    contract_symbol = _contract_symbol(fetched.underlying, fetched.expiration, fetched.strike, fetched.right)
    candidate = next(
        (
            row
            for row in window_rows
            if trade_at_ask_key in standards and _trigger_trade_at_ask(row, standards[trade_at_ask_key])
        ),
        max(window_rows, key=lambda row: _int(row.get("size"))),
    )
    trade_ts = _parse_thetadata_timestamp(candidate.get("trade_timestamp"))
    quote_ts = _parse_thetadata_timestamp(candidate.get("quote_timestamp"))
    quote = _quote_stats(candidate)
    price = _float(candidate.get("price"))
    size = _int(candidate.get("size"))
    price_vs_ask = _price_vs_ask(candidate)
    ask_touch_ratio = _ask_touch_ratio(candidate)
    window_statistics = _window_stats(window_rows, prior_window_volume)

    triggered: dict[str, Any] = {}
    order: list[str] = []
    if trade_at_ask_key in standards and _trigger_trade_at_ask(candidate, standards[trade_at_ask_key]):
        triggered[trade_at_ask_key] = {
            f(OPTION_EVENT_DETAIL_STATISTICS): {
                f(TRADE_PRICE): price,
                f(OPTION_EVENT_DETAIL_PRICE_VS_ASK): price_vs_ask,
                f(OPTION_EVENT_DETAIL_ASK_TOUCH_RATIO): ask_touch_ratio,
                f(QUOTE_BID): quote["bid"],
                f(QUOTE_ASK): quote["ask"],
                f(QUOTE_MID): quote["mid"],
            },
            f(OPTION_EVENT_DETAIL_CURRENT_STANDARD): _standard_by_registry_names(names, standards[trade_at_ask_key]),
        }
        order.append(trade_at_ask_key)
    if opening_key in standards and _trigger_opening_activity(window_statistics, standards[opening_key]):
        triggered[opening_key] = {
            f(OPTION_EVENT_DETAIL_STATISTICS): {
                f(WINDOW_TRADE_COUNT): window_statistics["window_trade_count"],
                f(WINDOW_VOLUME): window_statistics["window_volume"],
                f(WINDOW_NOTIONAL): window_statistics["window_notional"],
                f(FIRST_SEEN_IN_WINDOW): window_statistics["first_seen_in_window"],
                f(CONTRACT_PRIOR_WINDOW_VOLUME): window_statistics["contract_prior_window_volume"],
                f(VOLUME_VS_PRIOR_WINDOW_RATIO): window_statistics["volume_vs_prior_window_ratio"],
                f(VOLUME_PERCENTILE_20D_SAME_TIME): window_statistics["volume_percentile_20d_same_time"],
            },
            f(OPTION_EVENT_DETAIL_CURRENT_STANDARD): _standard_by_registry_names(names, standards[opening_key]),
        }
        order.append(opening_key)
    if fetched.iv_context and iv_key in standards and _trigger_iv_high(fetched.iv_context, standards[iv_key]):
        triggered[iv_key] = {
            f(OPTION_EVENT_DETAIL_STATISTICS): {
                f(IMPLIED_VOL): _float(fetched.iv_context.get("implied_vol")),
                f(EXPIRATION_CHAIN_CONTRACT_COUNT): fetched.iv_context.get("expiration_chain_contract_count"),
                f(IV_RANK_IN_EXPIRATION): fetched.iv_context.get("iv_rank_in_expiration"),
                f(IV_PERCENTILE_BY_EXPIRATION): _float(fetched.iv_context.get("iv_percentile_by_expiration")),
                f(IV_ZSCORE_BY_EXPIRATION): _float(fetched.iv_context.get("iv_zscore_by_expiration")),
            },
            f(OPTION_EVENT_DETAIL_CURRENT_STANDARD): _standard_by_registry_names(names, standards[iv_key]),
        }
        order.append(iv_key)

    if not triggered:
        return None

    event_id = _new_id("opt_evt")
    created_at = _iso(trade_ts) or window_start.isoformat()
    updated_at = fetched.standard_context.get("generated_at") or created_at
    detail_filename = f"{event_id}.csv"
    window_end = window_start + timedelta(seconds=SUPPORTED_TIMEFRAMES[fetched.timeframe])
    standard_context = {
        f(OPTION_EVENT_DETAIL_STANDARD_SOURCE): fetched.standard_context.get("standard_source"),
        f(OPTION_EVENT_DETAIL_STANDARD_ID): fetched.standard_context.get("standard_id"),
        f(GENERATED_AT): fetched.standard_context.get("generated_at"),
    }
    detail: dict[str, Any] = {
        f(OPTION_EVENT_DETAIL_EVENT_ID): event_id,
        f(TIMELINE_CREATED_AT): created_at,
        f(TIMELINE_UPDATED_AT): updated_at,
        f(OPTION_EVENT_DETAIL_STANDARD_CONTEXT): standard_context,
        f(OPTION_UNDERLYING): fetched.underlying,
        f(OPTION_EVENT_DETAIL_CONTRACT): {
            f(OPTION_EXPIRATION): fetched.expiration,
            f(OPTION_RIGHT_TYPE): fetched.right,
            f(OPTION_STRIKE): fetched.strike,
            f(OPTION_CONTRACT_SYMBOL): contract_symbol,
        },
        f(OPTION_EVENT_DETAIL_TRIGGERED_INDICATORS): triggered,
        f(OPTION_EVENT_DETAIL_EVIDENCE_WINDOW): {
            f(DATA_TIMEFRAME): fetched.timeframe,
            f(WINDOW_START): window_start.isoformat(),
            f(WINDOW_END): window_end.isoformat(),
        },
        f(OPTION_EVENT_DETAIL_TRIGGERING_TRADE): {
            f(TRADE_SIDE_TYPE): "ask_side" if trade_at_ask_key in triggered else None,
            f(TRADE_TIMESTAMP): created_at,
            f(TRADE_PRICE): price,
            f(TRADE_SIZE): size,
        },
        f(OPTION_EVENT_DETAIL_QUOTE_CONTEXT): {
            f(DATA_TIMESTAMP): _iso(quote_ts),
            f(QUOTE_BID): quote["bid"],
            f(QUOTE_ASK): quote["ask"],
            f(QUOTE_MID): quote["mid"],
            f(QUOTE_SPREAD): quote["spread"],
        },
        f(OPTION_EVENT_DETAIL_SOURCE_REFS): {
            f(OPTION_EVENT_DETAIL_PROVIDER): "ThetaData Terminal v3",
            f(OPTION_EVENT_DETAIL_RAW_PERSISTENCE): "not_persisted_by_default",
        },
    }
    if fetched.iv_context:
        detail[f(OPTION_EVENT_DETAIL_IV_CONTEXT)] = {
            f(IMPLIED_VOL): _float(fetched.iv_context.get("implied_vol")),
            f(IV_PERCENTILE_BY_EXPIRATION): _float(fetched.iv_context.get("iv_percentile_by_expiration")),
            f(IV_ZSCORE_BY_EXPIRATION): _float(fetched.iv_context.get("iv_zscore_by_expiration")),
        }
    row = {
        f(TIMELINE_ID): event_id,
        f(TIMELINE_HEADLINE): _event_headline(contract_symbol, order),
        f(TIMELINE_CREATED_AT): created_at,
        f(TIMELINE_UPDATED_AT): updated_at,
        f(TIMELINE_SYMBOLS): f"{fetched.underlying};{contract_symbol}",
        f(TIMELINE_SUMMARY): ";".join(order),
        f(TIMELINE_URL): detail_filename,
    }
    return EventRecord(row=row, detail=detail)


def clean(context: BundleContext, fetched: FetchedTradeQuote) -> StepResult:
    names = RegistryNames(context.registry_csv)
    timestamped_rows: list[tuple[datetime, dict[str, Any]]] = []
    for row in fetched.rows:
        timestamp = _parse_thetadata_timestamp(row.get("trade_timestamp"))
        if timestamp is not None:
            timestamped_rows.append((timestamp, row))
    timestamped_rows.sort(key=lambda item: item[0])

    windows: dict[str, list[dict[str, Any]]] = {}
    starts: dict[str, datetime] = {}
    for timestamp, row in timestamped_rows:
        start = _bucket_start_et(timestamp, fetched.timeframe)
        key = start.isoformat()
        starts[key] = start
        windows.setdefault(key, []).append(row)

    events: list[EventRecord] = []
    prior_volume = 0
    for key in sorted(windows):
        window_rows = windows[key]
        event = _build_event(names, fetched, starts[key], window_rows, prior_volume)
        prior_volume = sum(_int(row.get("size")) for row in window_rows)
        if event is not None:
            events.append(event)
            if len(events) >= fetched.max_events:
                break

    context.cleaned_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = context.cleaned_dir / "option_activity_event.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps({"row": event.row, "detail": event.detail}, sort_keys=True) + "\n")
    schema_path = context.cleaned_dir / "schema.json"
    schema_path.write_text(
        json.dumps({"option_activity_event": [names.payload(ref) for ref in CSV_FIELD_REFS]}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return StepResult(
        "succeeded",
        [str(jsonl_path), str(schema_path)],
        {
            "option_activity_event": len(events),
            "option_activity_event_detail": len(events),
            "option_trade_quote_rows_transient": len(fetched.rows),
        },
        warnings=[] if events else ["no option activity events satisfied the supplied current_standard"],
        details={"timezone": "America/New_York", "format": "jsonl", "window_count": len(windows)},
    )


def _read_cleaned_events(path: Path) -> list[EventRecord]:
    events: list[EventRecord] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        events.append(EventRecord(row=payload["row"], detail=payload["detail"]))
    return events


def save(context: BundleContext, clean_result: StepResult) -> StepResult:
    names = RegistryNames(context.registry_csv)
    fields = [names.payload(ref) for ref in CSV_FIELD_REFS]
    events = _read_cleaned_events(context.cleaned_dir / "option_activity_event.jsonl")
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    csv_path = context.saved_dir / "option_activity_event.csv"
    tmp_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with tmp_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows([event.row for event in events])
    os.replace(tmp_csv, csv_path)

    references = [str(csv_path)]
    url_field = names.payload(TIMELINE_URL)
    detail_fields = [
        names.payload(OPTION_EVENT_DETAIL_EVENT_ID),
        names.payload(TIMELINE_CREATED_AT),
        names.payload(TIMELINE_UPDATED_AT),
        names.payload(OPTION_UNDERLYING),
        names.payload(OPTION_EXPIRATION),
        names.payload(OPTION_RIGHT_TYPE),
        names.payload(OPTION_STRIKE),
        names.payload(OPTION_CONTRACT_SYMBOL),
        names.payload(OPTION_EVENT_DETAIL_TRIGGERED_INDICATORS),
        names.payload(OPTION_EVENT_DETAIL_EVIDENCE_WINDOW),
        names.payload(OPTION_EVENT_DETAIL_TRIGGERING_TRADE),
        names.payload(OPTION_EVENT_DETAIL_QUOTE_CONTEXT),
        names.payload(OPTION_EVENT_DETAIL_IV_CONTEXT),
        names.payload(OPTION_EVENT_DETAIL_SOURCE_REFS),
    ]
    contract_field = names.payload(OPTION_EVENT_DETAIL_CONTRACT)
    for event in events:
        detail_path = context.saved_dir / event.row[url_field]
        tmp_detail = detail_path.with_suffix(detail_path.suffix + ".tmp")
        detail = event.detail
        contract = detail.get(contract_field, {})
        detail_row = {
            names.payload(OPTION_EVENT_DETAIL_EVENT_ID): detail.get(names.payload(OPTION_EVENT_DETAIL_EVENT_ID)),
            names.payload(TIMELINE_CREATED_AT): detail.get(names.payload(TIMELINE_CREATED_AT)),
            names.payload(TIMELINE_UPDATED_AT): detail.get(names.payload(TIMELINE_UPDATED_AT)),
            names.payload(OPTION_UNDERLYING): detail.get(names.payload(OPTION_UNDERLYING)),
            names.payload(OPTION_EXPIRATION): contract.get(names.payload(OPTION_EXPIRATION)),
            names.payload(OPTION_RIGHT_TYPE): contract.get(names.payload(OPTION_RIGHT_TYPE)),
            names.payload(OPTION_STRIKE): contract.get(names.payload(OPTION_STRIKE)),
            names.payload(OPTION_CONTRACT_SYMBOL): contract.get(names.payload(OPTION_CONTRACT_SYMBOL)),
            names.payload(OPTION_EVENT_DETAIL_TRIGGERED_INDICATORS): json.dumps(detail.get(names.payload(OPTION_EVENT_DETAIL_TRIGGERED_INDICATORS), {}), separators=(",", ":")),
            names.payload(OPTION_EVENT_DETAIL_EVIDENCE_WINDOW): json.dumps(detail.get(names.payload(OPTION_EVENT_DETAIL_EVIDENCE_WINDOW), {}), separators=(",", ":")),
            names.payload(OPTION_EVENT_DETAIL_TRIGGERING_TRADE): json.dumps(detail.get(names.payload(OPTION_EVENT_DETAIL_TRIGGERING_TRADE), {}), separators=(",", ":")),
            names.payload(OPTION_EVENT_DETAIL_QUOTE_CONTEXT): json.dumps(detail.get(names.payload(OPTION_EVENT_DETAIL_QUOTE_CONTEXT), {}), separators=(",", ":")),
            names.payload(OPTION_EVENT_DETAIL_IV_CONTEXT): json.dumps(detail.get(names.payload(OPTION_EVENT_DETAIL_IV_CONTEXT), {}), separators=(",", ":")),
            names.payload(OPTION_EVENT_DETAIL_SOURCE_REFS): json.dumps(detail.get(names.payload(OPTION_EVENT_DETAIL_SOURCE_REFS), {}), separators=(",", ":")),
        }
        with tmp_detail.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=detail_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerow(detail_row)
        os.replace(tmp_detail, detail_path)
        references.append(str(detail_path))
    return StepResult(
        "succeeded",
        references,
        dict(clean_result.row_counts),
        warnings=list(clean_result.warnings),
        details={"format": "csv", "atomic_write": True},
    )


def write_receipt(
    context: BundleContext,
    *,
    status: str,
    fetch_result: StepResult | None = None,
    clean_result: StepResult | None = None,
    save_result: StepResult | None = None,
    error: BaseException | None = None,
) -> StepResult:
    context.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {"task_id": context.task_key.get("task_id"), "bundle": BUNDLE, "runs": []}
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
    existing.update({"task_id": context.task_key.get("task_id"), "bundle": BUNDLE})
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
