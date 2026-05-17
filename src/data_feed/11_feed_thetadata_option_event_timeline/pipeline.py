"""ThetaData option activity event timeline feed.

Development-stage final outputs are ``option_activity_event.csv`` and one
``<event_id>.csv`` detail artifact per emitted event. Provider trade/quote
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

from feed_availability.http import HttpClient, HttpResult
from feed_availability.sanitize import sanitize_url, sanitize_value
from feed_availability.secrets import load_secret_alias, public_secret_summary
from data_runtime.provider_policy import require_provider_execution_allowed

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
DEFAULT_REGISTRY_CSV = Path("/root/projects/trading-manager/scripts/registry/current.csv")
FEED = "11_feed_thetadata_option_event_timeline"
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


LOCAL_FIELD_NAMES = {
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
    "fld_OPD057": "bid_touch_ratio",
    "fld_OPD058": "trade_notional",
    "fld_OPD059": "trade_side_evidence",
    "fld_OPD060": "sweep_or_block_context",
    "fld_OPD061": "open_interest_context",
    "fld_OPD062": "opening_or_closing_context",
    "fld_OPD063": "iv_change",
    "fld_OPD064": "skew_direction",
    "fld_OPD065": "term_structure_direction",
    "fld_OPD066": "underlying_confirmation_or_divergence",
    "fld_OPD067": "direction_confidence",
    "fld_OPD068": "abnormality_evidence_coverage",
    "fld_OPD069": "trade_at_bid",
    "fld_OPD070": "max_price_vs_bid",
    "fld_OPD071": "min_bid_touch_ratio",
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
    open_interest_context: dict[str, Any] | None
    skew_context: dict[str, Any] | None
    term_structure_context: dict[str, Any] | None
    underlying_context: dict[str, Any] | None
    auto_context: dict[str, Any]
    request_evidence: dict[str, Any]
    secret_alias: dict[str, Any] | None
    max_events: int


class ThetaDataOptionEventTimelineError(ValueError):
    pass


class RegistryNames:
    """Resolve retained registry fields and stable code-local output field names."""

    def __init__(self, registry_csv: Path | None = DEFAULT_REGISTRY_CSV) -> None:
        self._rows: dict[str, dict[str, str]] = {}
        if registry_csv is None or not registry_csv.exists():
            return
        with registry_csv.open(newline="", encoding="utf-8") as handle:
            self._rows = {row["id"]: row for row in csv.DictReader(handle)}

    def field_name(self, ref: RegistryRef) -> str:
        try:
            field_name = LOCAL_FIELD_NAMES[ref.id]
        except KeyError as exc:
            raise ThetaDataOptionEventTimelineError(f"stable field id not found: {ref.id}") from exc
        row = self._rows.get(ref.id)
        if row is not None and row["kind"] not in ref.expected_kinds:
            raise ThetaDataOptionEventTimelineError(
                f"registry id {ref.id} expected kind in {ref.expected_kinds}, got kind={row['kind']}"
            )
        return field_name



# Local-output field ids. Registry rows validate retained ids when present;
# code-local names own emitted field names and must not be inferred from registry payload.
def field(item_id: str) -> RegistryRef:
    return RegistryRef(item_id, ("field", "identity_field", "path_field", "temporal_field", "classification_field", "text_field", "parameter_field"))


def data_kind(item_id: str) -> RegistryRef:
    return RegistryRef(item_id, ("data_kind",))


DATA_KIND = field("fld_EKIND001")
OPTION_UNDERLYING = field("fld_OPT001")
OPTION_EXPIRATION = field("fld_OPT002")
OPTION_RIGHT_TYPE = field("fld_OPT003")
OPTION_STRIKE = field("fld_OPT004")
DATA_TIMESTAMP = field("fld_OPT013")
TIMEFRAME = field("fld_OPT014")
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
OPTION_EVENT_TRIGGER_TRADE_AT_BID = field("fld_OPD069")
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
OPTION_EVENT_DETAIL_BID_TOUCH_RATIO = field("fld_OPD057")
OPTION_EVENT_DETAIL_TRADE_NOTIONAL = field("fld_OPD058")
OPTION_EVENT_DETAIL_TRADE_SIDE_EVIDENCE = field("fld_OPD059")
OPTION_EVENT_DETAIL_SWEEP_OR_BLOCK_CONTEXT = field("fld_OPD060")
OPTION_EVENT_DETAIL_OPEN_INTEREST_CONTEXT = field("fld_OPD061")
OPTION_EVENT_DETAIL_OPENING_OR_CLOSING_CONTEXT = field("fld_OPD062")
OPTION_EVENT_DETAIL_IV_CHANGE = field("fld_OPD063")
OPTION_EVENT_DETAIL_SKEW_DIRECTION = field("fld_OPD064")
OPTION_EVENT_DETAIL_TERM_STRUCTURE_DIRECTION = field("fld_OPD065")
OPTION_EVENT_DETAIL_UNDERLYING_CONFIRMATION = field("fld_OPD066")
OPTION_EVENT_DETAIL_DIRECTION_CONFIDENCE = field("fld_OPD067")
OPTION_EVENT_DETAIL_ABNORMALITY_EVIDENCE_COVERAGE = field("fld_OPD068")
OPTION_EVENT_STANDARD_MAX_PRICE_VS_BID = field("fld_OPD070")
OPTION_EVENT_STANDARD_MIN_BID_TOUCH_RATIO = field("fld_OPD071")

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
        raise ThetaDataOptionEventTimelineError(f"{FEED}.params.{key} is required")
    return value


def _parse_date(value: Any, key: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ThetaDataOptionEventTimelineError(f"{FEED}.params.{key} must be YYYY-MM-DD") from exc


def _normalize_right(value: Any) -> str:
    right = str(value).upper()
    aliases = {"C": "CALL", "CALL": "CALL", "P": "PUT", "PUT": "PUT"}
    if right not in aliases:
        raise ThetaDataOptionEventTimelineError(f"{FEED}.params.right must be CALL or PUT")
    return aliases[right]


def _normalize_strike(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ThetaDataOptionEventTimelineError(f"{FEED}.params.strike must be numeric") from exc


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
        raise ThetaDataOptionEventTimelineError(f"{FEED}.params.current_standard is required")
    indicators = {k: v for k, v in standard.items() if k != "standard_context" and isinstance(v, Mapping)}
    if not indicators:
        raise ThetaDataOptionEventTimelineError(f"{FEED}.params.current_standard must include indicator standards")
    context = dict(standard.get("standard_context") if isinstance(standard.get("standard_context"), Mapping) else {})
    context.setdefault("standard_source", "task_key_current_standard")
    context.setdefault("standard_id", _new_id("opt_evt_std"))
    context.setdefault("generated_at", context.get("standard_generated_at") or _now_et())
    context.pop("standard_generated_at", None)
    return {key: dict(value) for key, value in indicators.items()}, context



def _previous_weekday(value: date) -> date:
    prior = value - timedelta(days=1)
    while prior.weekday() >= 5:
        prior -= timedelta(days=1)
    return prior


def _next_weekly_expiration(expiration: str) -> str | None:
    try:
        return (date.fromisoformat(expiration) + timedelta(days=7)).isoformat()
    except ValueError:
        return None


def _flatten_contract_data(response_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for response_row in response_rows:
        contract = response_row.get("contract") if isinstance(response_row.get("contract"), Mapping) else {}
        data = response_row.get("data")
        if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
            for item in data:
                if isinstance(item, Mapping):
                    row = dict(item)
                    row["contract"] = dict(contract)
                    flattened.append(row)
    return flattened


def _safe_fetch_rows(
    client: HttpClient,
    base_url: str,
    endpoint: str,
    params: Mapping[str, str],
    label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = client.get(f"{base_url}{endpoint}", params=dict(params), headers={"Accept": "application/json"})
    evidence = {"label": label, "endpoint": sanitize_url(result.url), "http_status": result.status}
    if result.status is None or result.status < 200 or result.status >= 300:
        evidence["error"] = result.error_message or result.text()[:240]
        return [], evidence
    try:
        payload = result.json()
        response_rows = _response_rows(payload)
    except Exception as exc:  # context enrichment must expose missing coverage, not hide it
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        return [], evidence
    flattened = _flatten_contract_data(response_rows)
    evidence["row_count"] = len(flattened)
    return flattened, evidence


def _build_auto_context(
    *,
    client: HttpClient,
    base_url: str,
    underlying: str,
    expiration: str,
    right: str,
    strike: float,
    start_date: date,
    end_date: date,
    params: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    right_lower = right.lower()
    opposite_right = "put" if right == "CALL" else "call"
    prior_date = _parse_date(params.get("prior_context_date"), "prior_context_date") if params.get("prior_context_date") else _previous_weekday(start_date)
    term_expiration = str(params.get("term_structure_expiration") or _next_weekly_expiration(expiration) or expiration)
    interval = str(params.get("option_context_interval") or "1m")
    common = {
        "symbol": underlying,
        "strike": _thetadata_strike(strike),
        "format": "json",
    }
    iv_common = {**common, "interval": interval}
    evidence: list[dict[str, Any]] = []
    target_iv, ev = _safe_fetch_rows(
        client,
        base_url,
        "/v3/option/history/greeks/implied_volatility",
        {**iv_common, "expiration": expiration, "right": right_lower, "start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "target_history_implied_volatility",
    )
    evidence.append(ev)
    skew_iv, ev = _safe_fetch_rows(
        client,
        base_url,
        "/v3/option/history/greeks/implied_volatility",
        {**iv_common, "expiration": expiration, "right": opposite_right, "start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "opposite_right_history_implied_volatility",
    )
    evidence.append(ev)
    term_iv, ev = _safe_fetch_rows(
        client,
        base_url,
        "/v3/option/history/greeks/implied_volatility",
        {**iv_common, "expiration": term_expiration, "right": right_lower, "start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "term_structure_history_implied_volatility",
    )
    evidence.append(ev)
    current_oi, ev = _safe_fetch_rows(
        client,
        base_url,
        "/v3/option/history/open_interest",
        {**common, "expiration": expiration, "right": right_lower, "date": start_date.isoformat()},
        "target_open_interest_current_date",
    )
    evidence.append(ev)
    prior_oi, ev = _safe_fetch_rows(
        client,
        base_url,
        "/v3/option/history/open_interest",
        {**common, "expiration": expiration, "right": right_lower, "date": prior_date.isoformat()},
        "target_open_interest_prior_date",
    )
    evidence.append(ev)
    return {
        "enabled": True,
        "prior_context_date": prior_date.isoformat(),
        "term_structure_expiration": term_expiration,
        "option_context_interval": interval,
        "target_iv_rows": target_iv,
        "skew_iv_rows": skew_iv,
        "term_iv_rows": term_iv,
        "current_oi_rows": current_oi,
        "prior_oi_rows": prior_oi,
    }, evidence

def build_context(task_key: dict[str, Any], run_id: str) -> FeedContext:
    if task_key.get("feed") != FEED:
        raise ThetaDataOptionEventTimelineError(f"task_key.feed must be {FEED}")
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


def fetch(context: FeedContext, *, client: HttpClient | None = None) -> tuple[StepResult, FetchedTradeQuote]:
    params = dict(context.task_key.get("params") or {})
    underlying = str(_required(params, "underlying")).upper()
    expiration = str(_required(params, "expiration"))
    right = _normalize_right(_required(params, "right"))
    strike = _normalize_strike(_required(params, "strike"))
    start_date = _parse_date(_required(params, "start_date"), "start_date")
    end_date = _parse_date(_required(params, "end_date"), "end_date")
    if end_date < start_date:
        raise ThetaDataOptionEventTimelineError(f"{FEED}.params.end_date must be on or after start_date")
    timeframe = str(_required(params, "timeframe"))
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ThetaDataOptionEventTimelineError(
            f"unsupported timeframe {timeframe!r}; supported={sorted(SUPPORTED_TIMEFRAMES)}"
        )
    current_standard, standard_context = _current_standard(params)
    max_events = int(params.get("max_events", 100))
    base_url = str(params.get("thetadata_base_url") or "http://127.0.0.1:25503").rstrip("/")
    timeout = int(params.get("timeout_seconds", 30))
    if client is None:
        require_provider_execution_allowed(
            context.task_key,
            provider="thetadata",
            endpoint_family="option_event_timeline",
            requested_symbols=1,
            requested_requests=4,
        )
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

    auto_context: dict[str, Any] = {"enabled": False}
    auto_context_evidence: list[dict[str, Any]] = []
    if params.get("auto_enrich_option_context"):
        auto_context, auto_context_evidence = _build_auto_context(
            client=client,
            base_url=base_url,
            underlying=underlying,
            expiration=expiration,
            right=right,
            strike=strike,
            start_date=start_date,
            end_date=end_date,
            params=params,
        )

    context.run_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "endpoint": sanitize_url(result.url),
        "http_status": result.status,
        "response_contract_count": len(response_rows),
        "source_row_count": len(rows),
        "auto_context_request_count": len(auto_context_evidence),
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
                "params": sanitize_value({**request_params, "timeframe": timeframe, "max_events": max_events}),
                "current_standard": sanitize_value(current_standard),
                "standard_context": sanitize_value(standard_context),
                "request": evidence,
                "auto_context_requests": sanitize_value(auto_context_evidence),
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
        open_interest_context=dict(params["open_interest_context"]) if isinstance(params.get("open_interest_context"), Mapping) else None,
        skew_context=dict(params["skew_context"]) if isinstance(params.get("skew_context"), Mapping) else None,
        term_structure_context=dict(params["term_structure_context"]) if isinstance(params.get("term_structure_context"), Mapping) else None,
        underlying_context=dict(params["underlying_context"]) if isinstance(params.get("underlying_context"), Mapping) else None,
        auto_context=auto_context,
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


def _price_vs_bid(row: Mapping[str, Any]) -> float | None:
    price = _float(row.get("price"))
    bid = _float(row.get("bid"))
    return bid - price if price is not None and bid is not None else None


def _ask_touch_ratio(row: Mapping[str, Any]) -> float | None:
    price = _float(row.get("price"))
    bid = _float(row.get("bid"))
    ask = _float(row.get("ask"))
    if price is None or bid is None or ask is None:
        return None
    if ask == bid:
        return 1.0 if price >= ask else 0.0
    return (price - bid) / (ask - bid)


def _bid_touch_ratio(row: Mapping[str, Any]) -> float | None:
    price = _float(row.get("price"))
    bid = _float(row.get("bid"))
    ask = _float(row.get("ask"))
    if price is None or bid is None or ask is None:
        return None
    if ask == bid:
        return 1.0 if price <= bid else 0.0
    return (ask - price) / (ask - bid)


def _trade_notional(row: Mapping[str, Any]) -> float | None:
    price = _float(row.get("price"))
    if price is None:
        return None
    return price * _int(row.get("size"))


def _trade_side_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    ask_ratio = _ask_touch_ratio(row)
    bid_ratio = _bid_touch_ratio(row)
    price = _float(row.get("price"))
    bid = _float(row.get("bid"))
    ask = _float(row.get("ask"))
    if price is None or bid is None or ask is None or ask_ratio is None or bid_ratio is None:
        side = "unknown_quote_context_missing"
        status = "missing"
    elif price > ask:
        side = "above_ask"
        status = "present"
    elif price < bid:
        side = "below_bid"
        status = "present"
    elif ask_ratio >= 0.95:
        side = "ask_side"
        status = "present"
    elif bid_ratio >= 0.95:
        side = "bid_side"
        status = "present"
    else:
        side = "inside_spread_or_midpoint"
        status = "present"
    return {
        "coverage_status": status,
        "classification_method": "quote_touch_inferred",
        "trade_side_type": side,
        "ask_touch_ratio": ask_ratio,
        "bid_touch_ratio": bid_ratio,
        "price": price,
        "bid": bid,
        "ask": ask,
    }


def _sweep_or_block_context(row: Mapping[str, Any], standard: Mapping[str, Any]) -> dict[str, Any]:
    size = _int(row.get("size"))
    notional = _trade_notional(row)
    condition = row.get("condition")
    sweep_flag = row.get("is_sweep")
    min_block_size = _float(standard.get("min_block_trade_size"))
    min_block_notional = _float(standard.get("min_block_notional"))
    sweep_codes = {str(item) for item in standard.get("sweep_condition_codes", [])} if isinstance(standard.get("sweep_condition_codes"), Sequence) and not isinstance(standard.get("sweep_condition_codes"), (str, bytes)) else set()
    is_block = (min_block_size is not None and size >= min_block_size) or (
        min_block_notional is not None and notional is not None and notional >= min_block_notional
    )
    is_sweep = bool(sweep_flag) or (condition is not None and str(condition) in sweep_codes)
    if is_sweep and is_block:
        classification = "sweep_block"
    elif is_sweep:
        classification = "sweep_trade"
    elif is_block:
        classification = "block_trade"
    elif min_block_size is None and min_block_notional is None and not sweep_codes and sweep_flag is None:
        classification = "not_evaluated_missing_standard_or_provider_flag"
    else:
        classification = "ordinary_print"
    return {
        "coverage_status": "present" if classification != "not_evaluated_missing_standard_or_provider_flag" else "missing",
        "classification": classification,
        "condition": condition,
        "is_sweep_provider_flag": sweep_flag if sweep_flag is not None else None,
        "trade_size": size,
        "trade_notional": notional,
        "min_block_trade_size": min_block_size,
        "min_block_notional": min_block_notional,
        "sweep_condition_codes": sorted(sweep_codes),
    }


def _open_interest_context(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {"coverage_status": "missing", "open_interest_change": None, "source": None}
    before = _float(raw.get("open_interest_before"))
    after = _float(raw.get("open_interest_after"))
    change = _float(raw.get("open_interest_change"))
    if change is None and before is not None and after is not None:
        change = after - before
    return {
        "coverage_status": "present" if change is not None or before is not None or after is not None else "missing",
        "open_interest_before": before,
        "open_interest_after": after,
        "open_interest_change": change,
        "source": raw.get("source") or raw.get("source_ref"),
    }


def _opening_or_closing_context(oi_context: Mapping[str, Any], window_statistics: Mapping[str, Any]) -> dict[str, Any]:
    change = _float(oi_context.get("open_interest_change"))
    volume = _int(window_statistics.get("window_volume"))
    if change is not None:
        if change > 0:
            classification = "net_opening_activity"
        elif change < 0:
            classification = "net_closing_activity"
        else:
            classification = "no_open_interest_change"
        status = "present"
    elif window_statistics.get("first_seen_in_window"):
        classification = "possible_opening_activity_volume_only"
        status = "partial"
    else:
        classification = "unknown_opening_or_closing"
        status = "missing"
    return {
        "coverage_status": status,
        "classification": classification,
        "open_interest_change": change,
        "window_volume": volume,
        "first_seen_in_window": window_statistics.get("first_seen_in_window"),
    }


def _iv_context(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {"coverage_status": "missing", "implied_vol": None, "iv_change": None}
    implied = _float(raw.get("implied_vol"))
    prior = _float(raw.get("prior_implied_vol"))
    change = _float(raw.get("iv_change"))
    if change is None and implied is not None and prior is not None:
        change = implied - prior
    return {
        "coverage_status": "present" if implied is not None or change is not None else "missing",
        "implied_vol": implied,
        "prior_implied_vol": prior,
        "iv_change": change,
        "iv_percentile_by_expiration": _float(raw.get("iv_percentile_by_expiration")),
        "iv_zscore_by_expiration": _float(raw.get("iv_zscore_by_expiration")),
    }


def _simple_direction_context(raw: Mapping[str, Any] | None, key: str) -> dict[str, Any]:
    if not raw:
        return {"coverage_status": "missing", key: None}
    value = raw.get(key) or raw.get("direction") or raw.get("classification")
    return {"coverage_status": "present" if value not in (None, "") else "missing", key: value, "source": raw.get("source") or raw.get("source_ref")}


def _underlying_confirmation_context(raw: Mapping[str, Any] | None, right: str, side_type: str) -> dict[str, Any]:
    if not raw:
        return {"coverage_status": "missing", "classification": None, "underlying_return": None}
    underlying_return = _float(raw.get("underlying_return") or raw.get("underlying_return_during_window"))
    expected_sign = None
    if side_type in {"ask_side", "above_ask"} and right == "CALL":
        expected_sign = 1
    elif side_type in {"ask_side", "above_ask"} and right == "PUT":
        expected_sign = -1
    elif side_type in {"bid_side", "below_bid"} and right == "CALL":
        expected_sign = -1
    elif side_type in {"bid_side", "below_bid"} and right == "PUT":
        expected_sign = 1
    if underlying_return is None or expected_sign is None:
        classification = "unknown_underlying_confirmation"
    elif underlying_return == 0:
        classification = "underlying_neutral"
    elif underlying_return * expected_sign > 0:
        classification = "underlying_confirming"
    else:
        classification = "underlying_diverging"
    return {
        "coverage_status": "present" if underlying_return is not None else "missing",
        "classification": classification,
        "underlying_return": underlying_return,
        "source": raw.get("source") or raw.get("source_ref"),
    }


def _direction_confidence(
    *,
    right: str,
    side_evidence: Mapping[str, Any],
    sweep_or_block: Mapping[str, Any],
    opening_or_closing: Mapping[str, Any],
    oi_context: Mapping[str, Any],
    iv_context: Mapping[str, Any],
    skew_context: Mapping[str, Any],
    term_context: Mapping[str, Any],
    underlying_context: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    side_type = str(side_evidence.get("trade_side_type"))
    if side_type in {"ask_side", "above_ask"} and right == "CALL":
        hypothesis = "bullish_activity"
    elif side_type in {"ask_side", "above_ask"} and right == "PUT":
        hypothesis = "bearish_activity"
    elif side_type in {"bid_side", "below_bid"} and right == "CALL":
        hypothesis = "bearish_activity_or_call_selling"
    elif side_type in {"bid_side", "below_bid"} and right == "PUT":
        hypothesis = "bullish_activity_or_put_selling"
    elif side_type == "inside_spread_or_midpoint":
        hypothesis = "mixed_or_conflicting_activity"
    else:
        hypothesis = "unknown_direction_activity"

    required = {
        "call_put_side": True,
        "aggressor_or_quote_side": side_evidence.get("coverage_status") == "present",
        "ask_bid_touch_context": side_evidence.get("ask_touch_ratio") is not None and side_evidence.get("bid_touch_ratio") is not None,
        "sweep_or_block_context": sweep_or_block.get("coverage_status") == "present",
        "opening_or_closing_context": opening_or_closing.get("coverage_status") == "present",
        "open_interest_or_oi_change": oi_context.get("coverage_status") == "present",
        "iv_level_and_change": iv_context.get("coverage_status") == "present" and iv_context.get("iv_change") is not None,
        "skew_direction": skew_context.get("coverage_status") == "present",
        "term_structure_direction": term_context.get("coverage_status") == "present",
        "underlying_confirmation_or_divergence": underlying_context.get("coverage_status") == "present",
    }
    missing = [key for key, present in required.items() if not present]
    score = (len(required) - len(missing)) / len(required)
    coverage = {
        "coverage_status": "complete" if not missing else "partial",
        "abnormality_coverage_complete": not missing,
        "present_fields": [key for key, present in required.items() if present],
        "missing_fields": missing,
    }
    confidence = {
        "direction_hypothesis": hypothesis,
        "confidence_status": "evidence_complete" if not missing else "insufficient_evidence",
        "confidence_score": round(score, 3),
        "abnormality_coverage_complete": not missing,
        "missing_fields": missing,
    }
    return confidence, coverage



def _row_timestamp(row: Mapping[str, Any]) -> datetime | None:
    return _parse_thetadata_timestamp(row.get("timestamp"))


def _row_at_or_before(rows: Sequence[Mapping[str, Any]], timestamp: datetime | None) -> dict[str, Any] | None:
    if timestamp is None:
        return None
    best: tuple[datetime, Mapping[str, Any]] | None = None
    for row in rows:
        row_ts = _row_timestamp(row)
        if row_ts is None or row_ts > timestamp:
            continue
        if best is None or row_ts > best[0]:
            best = (row_ts, row)
    return dict(best[1]) if best is not None else None


def _valid_iv_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    valid: list[Mapping[str, Any]] = []
    for row in rows:
        implied = _float(row.get("implied_vol"))
        iv_error = _float(row.get("iv_error"))
        if implied is None or implied <= 0:
            continue
        if iv_error is not None and iv_error >= 50:
            continue
        valid.append(row)
    return valid


def _first_row(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    return dict(rows[0]) if rows else None


def _auto_event_context(fetched: FetchedTradeQuote, window_start: datetime, trade_ts: datetime | None) -> dict[str, Any]:
    auto = fetched.auto_context if isinstance(fetched.auto_context, Mapping) else {}
    if not auto.get("enabled"):
        return {}
    target_rows = auto.get("target_iv_rows") if isinstance(auto.get("target_iv_rows"), Sequence) else []
    skew_rows = auto.get("skew_iv_rows") if isinstance(auto.get("skew_iv_rows"), Sequence) else []
    term_rows = auto.get("term_iv_rows") if isinstance(auto.get("term_iv_rows"), Sequence) else []
    target_rows = _valid_iv_rows(target_rows)
    skew_rows = _valid_iv_rows(skew_rows)
    term_rows = _valid_iv_rows(term_rows)
    current = _row_at_or_before(target_rows, trade_ts)
    prior = _row_at_or_before(target_rows, window_start)
    opposite = _row_at_or_before(skew_rows, trade_ts)
    term = _row_at_or_before(term_rows, trade_ts)

    current_iv = _float(current.get("implied_vol")) if current else None
    prior_iv = _float(prior.get("implied_vol")) if prior else None
    iv_change = current_iv - prior_iv if current_iv is not None and prior_iv is not None else None

    current_oi = _first_row(auto.get("current_oi_rows", []))
    prior_oi = _first_row(auto.get("prior_oi_rows", []))
    current_oi_value = _float(current_oi.get("open_interest")) if current_oi else None
    prior_oi_value = _float(prior_oi.get("open_interest")) if prior_oi else None

    opposite_iv = _float(opposite.get("implied_vol")) if opposite else None
    skew_direction = None
    if current_iv is not None and opposite_iv is not None:
        call_iv = current_iv if fetched.right == "CALL" else opposite_iv
        put_iv = opposite_iv if fetched.right == "CALL" else current_iv
        diff = call_iv - put_iv
        if abs(diff) < 0.005:
            skew_direction = "balanced_call_put_skew"
        elif diff > 0:
            skew_direction = "call_skew_richening"
        else:
            skew_direction = "put_skew_richening"

    term_iv = _float(term.get("implied_vol")) if term else None
    term_direction = None
    if current_iv is not None and term_iv is not None:
        diff = current_iv - term_iv
        if abs(diff) < 0.005:
            term_direction = "flat_term_structure"
        elif diff > 0:
            term_direction = "front_month_richening"
        else:
            term_direction = "back_month_richening"

    underlying_current = _float(current.get("underlying_price")) if current else None
    underlying_prior = _float(prior.get("underlying_price")) if prior else None
    underlying_return = (underlying_current - underlying_prior) / underlying_prior if underlying_current is not None and underlying_prior not in (None, 0) else None

    context: dict[str, Any] = {}
    if current_iv is not None or prior_iv is not None:
        context["iv_context"] = {
            "implied_vol": current_iv,
            "prior_implied_vol": prior_iv,
            "iv_change": iv_change,
            "source": "thetadata_history_greeks_implied_volatility",
            "current_timestamp": current.get("timestamp") if current else None,
            "prior_timestamp": prior.get("timestamp") if prior else None,
        }
    if current_oi_value is not None or prior_oi_value is not None:
        context["open_interest_context"] = {
            "open_interest_before": prior_oi_value,
            "open_interest_after": current_oi_value,
            "source": "thetadata_history_open_interest",
            "current_date": fetched.start_date.isoformat(),
            "prior_date": auto.get("prior_context_date"),
        }
    if skew_direction is not None:
        context["skew_context"] = {
            "skew_direction": skew_direction,
            "target_implied_vol": current_iv,
            "opposite_right_implied_vol": opposite_iv,
            "source": "thetadata_history_greeks_implied_volatility_same_strike_opposite_right",
        }
    if term_direction is not None:
        context["term_structure_context"] = {
            "term_structure_direction": term_direction,
            "front_expiration": fetched.expiration,
            "back_expiration": auto.get("term_structure_expiration"),
            "front_implied_vol": current_iv,
            "back_implied_vol": term_iv,
            "source": "thetadata_history_greeks_implied_volatility_same_strike_next_expiration",
        }
    if underlying_return is not None:
        context["underlying_context"] = {
            "underlying_return_during_window": underlying_return,
            "underlying_price_before": underlying_prior,
            "underlying_price_after": underlying_current,
            "source": "thetadata_history_greeks_underlying_price",
        }
    return context

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


def _trigger_trade_at_bid(row: Mapping[str, Any], standard: Mapping[str, Any]) -> bool:
    price_vs_bid = _price_vs_bid(row)
    bid_touch_ratio = _bid_touch_ratio(row)
    max_price_vs_bid = _float(standard.get("max_price_vs_bid"))
    min_bid_touch_ratio = _float(standard.get("min_bid_touch_ratio"))
    if price_vs_bid is None or bid_touch_ratio is None:
        return False
    if max_price_vs_bid is not None and price_vs_bid > max_price_vs_bid:
        return False
    if min_bid_touch_ratio is not None and bid_touch_ratio < min_bid_touch_ratio:
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
    f = names.field_name
    mapping = {
        "max_price_vs_ask": f(OPTION_EVENT_STANDARD_MAX_PRICE_VS_ASK),
        "min_ask_touch_ratio": f(OPTION_EVENT_STANDARD_MIN_ASK_TOUCH_RATIO),
        "max_price_vs_bid": f(OPTION_EVENT_STANDARD_MAX_PRICE_VS_BID),
        "min_bid_touch_ratio": f(OPTION_EVENT_STANDARD_MIN_BID_TOUCH_RATIO),
        "min_window_volume": f(OPTION_EVENT_STANDARD_MIN_WINDOW_VOLUME),
        "min_volume_percentile_20d_same_time": f(OPTION_EVENT_STANDARD_MIN_VOLUME_PERCENTILE_20D_SAME_TIME),
        "min_iv_percentile_by_expiration": f(OPTION_EVENT_STANDARD_MIN_IV_PERCENTILE_BY_EXPIRATION),
        "min_iv_zscore_by_expiration": f(OPTION_EVENT_STANDARD_MIN_IV_ZSCORE_BY_EXPIRATION),
    }
    return {mapping.get(key, key): value for key, value in standard.items()}


def _event_headline(contract_symbol: str, triggered: Sequence[str]) -> str:
    phrases = {
        "trade_at_ask": "ask-side activity",
        "trade_at_bid": "bid-side activity",
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
    f = names.field_name
    standards = fetched.current_standard
    trade_at_ask_key = f(OPTION_EVENT_TRIGGER_TRADE_AT_ASK)
    trade_at_bid_key = f(OPTION_EVENT_TRIGGER_TRADE_AT_BID)
    opening_key = f(OPTION_EVENT_TRIGGER_OPENING_ACTIVITY)
    iv_key = f(OPTION_EVENT_TRIGGER_IV_HIGH_CROSS_SECTION)
    contract_symbol = _contract_symbol(fetched.underlying, fetched.expiration, fetched.strike, fetched.right)
    ask_candidate = next(
        (
            row
            for row in window_rows
            if trade_at_ask_key in standards and _trigger_trade_at_ask(row, standards[trade_at_ask_key])
        ),
        None,
    )
    bid_candidate = next(
        (
            row
            for row in window_rows
            if trade_at_bid_key in standards and _trigger_trade_at_bid(row, standards[trade_at_bid_key])
        ),
        None,
    )
    candidate = ask_candidate or bid_candidate or max(window_rows, key=lambda row: _int(row.get("size")))
    trade_ts = _parse_thetadata_timestamp(candidate.get("trade_timestamp"))
    quote_ts = _parse_thetadata_timestamp(candidate.get("quote_timestamp"))
    quote = _quote_stats(candidate)
    price = _float(candidate.get("price"))
    size = _int(candidate.get("size"))
    price_vs_ask = _price_vs_ask(candidate)
    ask_touch_ratio = _ask_touch_ratio(candidate)
    bid_touch_ratio = _bid_touch_ratio(candidate)
    trade_notional = _trade_notional(candidate)
    side_evidence = _trade_side_evidence(candidate)
    auto_context = _auto_event_context(fetched, window_start, trade_ts)
    window_statistics = _window_stats(window_rows, prior_window_volume)
    sweep_standard = standards.get("sweep_or_block_activity") if isinstance(standards.get("sweep_or_block_activity"), Mapping) else {}
    sweep_or_block = _sweep_or_block_context(candidate, sweep_standard)
    oi_context = _open_interest_context(
        fetched.open_interest_context or auto_context.get("open_interest_context")
        if isinstance(auto_context.get("open_interest_context"), Mapping) or fetched.open_interest_context
        else None
    )
    opening_or_closing = _opening_or_closing_context(oi_context, window_statistics)
    iv_context = _iv_context(
        fetched.iv_context or auto_context.get("iv_context")
        if isinstance(auto_context.get("iv_context"), Mapping) or fetched.iv_context
        else None
    )
    skew_context = _simple_direction_context(
        fetched.skew_context or auto_context.get("skew_context")
        if isinstance(auto_context.get("skew_context"), Mapping) or fetched.skew_context
        else None,
        "skew_direction",
    )
    term_context = _simple_direction_context(
        fetched.term_structure_context or auto_context.get("term_structure_context")
        if isinstance(auto_context.get("term_structure_context"), Mapping) or fetched.term_structure_context
        else None,
        "term_structure_direction",
    )
    underlying_context = _underlying_confirmation_context(
        fetched.underlying_context or auto_context.get("underlying_context")
        if isinstance(auto_context.get("underlying_context"), Mapping) or fetched.underlying_context
        else None,
        fetched.right,
        str(side_evidence.get("trade_side_type")),
    )
    direction_confidence, evidence_coverage = _direction_confidence(
        right=fetched.right,
        side_evidence=side_evidence,
        sweep_or_block=sweep_or_block,
        opening_or_closing=opening_or_closing,
        oi_context=oi_context,
        iv_context=iv_context,
        skew_context=skew_context,
        term_context=term_context,
        underlying_context=underlying_context,
    )

    triggered: dict[str, Any] = {}
    order: list[str] = []
    if trade_at_ask_key in standards and _trigger_trade_at_ask(candidate, standards[trade_at_ask_key]):
        triggered[trade_at_ask_key] = {
            f(OPTION_EVENT_DETAIL_STATISTICS): {
                f(TRADE_PRICE): price,
                f(OPTION_EVENT_DETAIL_PRICE_VS_ASK): price_vs_ask,
                f(OPTION_EVENT_DETAIL_ASK_TOUCH_RATIO): ask_touch_ratio,
                f(OPTION_EVENT_DETAIL_BID_TOUCH_RATIO): bid_touch_ratio,
                f(OPTION_EVENT_DETAIL_TRADE_NOTIONAL): trade_notional,
                f(QUOTE_BID): quote["bid"],
                f(QUOTE_ASK): quote["ask"],
                f(QUOTE_MID): quote["mid"],
            },
            f(OPTION_EVENT_DETAIL_CURRENT_STANDARD): _standard_by_registry_names(names, standards[trade_at_ask_key]),
        }
        order.append(trade_at_ask_key)
    if trade_at_bid_key in standards and _trigger_trade_at_bid(candidate, standards[trade_at_bid_key]):
        triggered[trade_at_bid_key] = {
            f(OPTION_EVENT_DETAIL_STATISTICS): {
                f(TRADE_PRICE): price,
                f(OPTION_EVENT_DETAIL_BID_TOUCH_RATIO): bid_touch_ratio,
                f(OPTION_EVENT_DETAIL_TRADE_NOTIONAL): trade_notional,
                f(QUOTE_BID): quote["bid"],
                f(QUOTE_ASK): quote["ask"],
                f(QUOTE_MID): quote["mid"],
            },
            f(OPTION_EVENT_DETAIL_CURRENT_STANDARD): _standard_by_registry_names(names, standards[trade_at_bid_key]),
        }
        order.append(trade_at_bid_key)
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
            f(TIMEFRAME): fetched.timeframe,
            f(WINDOW_START): window_start.isoformat(),
            f(WINDOW_END): window_end.isoformat(),
        },
        f(OPTION_EVENT_DETAIL_TRIGGERING_TRADE): {
            f(TRADE_SIDE_TYPE): side_evidence.get("trade_side_type"),
            f(TRADE_TIMESTAMP): created_at,
            f(TRADE_PRICE): price,
            f(TRADE_SIZE): size,
            f(OPTION_EVENT_DETAIL_TRADE_NOTIONAL): trade_notional,
            f(OPTION_EVENT_DETAIL_ASK_TOUCH_RATIO): ask_touch_ratio,
            f(OPTION_EVENT_DETAIL_BID_TOUCH_RATIO): bid_touch_ratio,
        },
        f(OPTION_EVENT_DETAIL_TRADE_SIDE_EVIDENCE): side_evidence,
        f(OPTION_EVENT_DETAIL_SWEEP_OR_BLOCK_CONTEXT): sweep_or_block,
        f(OPTION_EVENT_DETAIL_OPEN_INTEREST_CONTEXT): oi_context,
        f(OPTION_EVENT_DETAIL_OPENING_OR_CLOSING_CONTEXT): opening_or_closing,
        f(OPTION_EVENT_DETAIL_IV_CHANGE): iv_context.get("iv_change"),
        f(OPTION_EVENT_DETAIL_SKEW_DIRECTION): skew_context.get("skew_direction"),
        f(OPTION_EVENT_DETAIL_TERM_STRUCTURE_DIRECTION): term_context.get("term_structure_direction"),
        f(OPTION_EVENT_DETAIL_UNDERLYING_CONFIRMATION): underlying_context,
        f(OPTION_EVENT_DETAIL_DIRECTION_CONFIDENCE): direction_confidence,
        f(OPTION_EVENT_DETAIL_ABNORMALITY_EVIDENCE_COVERAGE): evidence_coverage,
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
    detail[f(OPTION_EVENT_DETAIL_IV_CONTEXT)] = {
        f(IMPLIED_VOL): iv_context.get("implied_vol"),
        f(OPTION_EVENT_DETAIL_IV_CHANGE): iv_context.get("iv_change"),
        f(IV_PERCENTILE_BY_EXPIRATION): iv_context.get("iv_percentile_by_expiration"),
        f(IV_ZSCORE_BY_EXPIRATION): iv_context.get("iv_zscore_by_expiration"),
        "coverage_status": iv_context.get("coverage_status"),
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


def clean(context: FeedContext, fetched: FetchedTradeQuote) -> StepResult:
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
        json.dumps({"option_activity_event": [names.field_name(ref) for ref in CSV_FIELD_REFS]}, indent=2, sort_keys=True)
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


def save(context: FeedContext, clean_result: StepResult) -> StepResult:
    names = RegistryNames(context.registry_csv)
    fields = [names.field_name(ref) for ref in CSV_FIELD_REFS]
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
    url_field = names.field_name(TIMELINE_URL)
    detail_fields = [
        names.field_name(OPTION_EVENT_DETAIL_EVENT_ID),
        names.field_name(TIMELINE_CREATED_AT),
        names.field_name(TIMELINE_UPDATED_AT),
        names.field_name(OPTION_UNDERLYING),
        names.field_name(OPTION_EXPIRATION),
        names.field_name(OPTION_RIGHT_TYPE),
        names.field_name(OPTION_STRIKE),
        names.field_name(OPTION_CONTRACT_SYMBOL),
        names.field_name(OPTION_EVENT_DETAIL_TRIGGERED_INDICATORS),
        names.field_name(OPTION_EVENT_DETAIL_EVIDENCE_WINDOW),
        names.field_name(OPTION_EVENT_DETAIL_TRIGGERING_TRADE),
        names.field_name(OPTION_EVENT_DETAIL_TRADE_SIDE_EVIDENCE),
        names.field_name(OPTION_EVENT_DETAIL_SWEEP_OR_BLOCK_CONTEXT),
        names.field_name(OPTION_EVENT_DETAIL_OPEN_INTEREST_CONTEXT),
        names.field_name(OPTION_EVENT_DETAIL_OPENING_OR_CLOSING_CONTEXT),
        names.field_name(OPTION_EVENT_DETAIL_IV_CONTEXT),
        names.field_name(OPTION_EVENT_DETAIL_IV_CHANGE),
        names.field_name(OPTION_EVENT_DETAIL_SKEW_DIRECTION),
        names.field_name(OPTION_EVENT_DETAIL_TERM_STRUCTURE_DIRECTION),
        names.field_name(OPTION_EVENT_DETAIL_UNDERLYING_CONFIRMATION),
        names.field_name(OPTION_EVENT_DETAIL_DIRECTION_CONFIDENCE),
        names.field_name(OPTION_EVENT_DETAIL_ABNORMALITY_EVIDENCE_COVERAGE),
        names.field_name(OPTION_EVENT_DETAIL_QUOTE_CONTEXT),
        names.field_name(OPTION_EVENT_DETAIL_SOURCE_REFS),
    ]
    contract_field = names.field_name(OPTION_EVENT_DETAIL_CONTRACT)
    for event in events:
        detail_path = context.saved_dir / event.row[url_field]
        tmp_detail = detail_path.with_suffix(detail_path.suffix + ".tmp")
        detail = event.detail
        contract = detail.get(contract_field, {})
        detail_row = {
            names.field_name(OPTION_EVENT_DETAIL_EVENT_ID): detail.get(names.field_name(OPTION_EVENT_DETAIL_EVENT_ID)),
            names.field_name(TIMELINE_CREATED_AT): detail.get(names.field_name(TIMELINE_CREATED_AT)),
            names.field_name(TIMELINE_UPDATED_AT): detail.get(names.field_name(TIMELINE_UPDATED_AT)),
            names.field_name(OPTION_UNDERLYING): detail.get(names.field_name(OPTION_UNDERLYING)),
            names.field_name(OPTION_EXPIRATION): contract.get(names.field_name(OPTION_EXPIRATION)),
            names.field_name(OPTION_RIGHT_TYPE): contract.get(names.field_name(OPTION_RIGHT_TYPE)),
            names.field_name(OPTION_STRIKE): contract.get(names.field_name(OPTION_STRIKE)),
            names.field_name(OPTION_CONTRACT_SYMBOL): contract.get(names.field_name(OPTION_CONTRACT_SYMBOL)),
            names.field_name(OPTION_EVENT_DETAIL_TRIGGERED_INDICATORS): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_TRIGGERED_INDICATORS), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_EVIDENCE_WINDOW): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_EVIDENCE_WINDOW), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_TRIGGERING_TRADE): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_TRIGGERING_TRADE), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_TRADE_SIDE_EVIDENCE): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_TRADE_SIDE_EVIDENCE), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_SWEEP_OR_BLOCK_CONTEXT): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_SWEEP_OR_BLOCK_CONTEXT), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_OPEN_INTEREST_CONTEXT): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_OPEN_INTEREST_CONTEXT), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_OPENING_OR_CLOSING_CONTEXT): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_OPENING_OR_CLOSING_CONTEXT), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_IV_CONTEXT): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_IV_CONTEXT), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_IV_CHANGE): detail.get(names.field_name(OPTION_EVENT_DETAIL_IV_CHANGE)),
            names.field_name(OPTION_EVENT_DETAIL_SKEW_DIRECTION): detail.get(names.field_name(OPTION_EVENT_DETAIL_SKEW_DIRECTION)),
            names.field_name(OPTION_EVENT_DETAIL_TERM_STRUCTURE_DIRECTION): detail.get(names.field_name(OPTION_EVENT_DETAIL_TERM_STRUCTURE_DIRECTION)),
            names.field_name(OPTION_EVENT_DETAIL_UNDERLYING_CONFIRMATION): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_UNDERLYING_CONFIRMATION), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_DIRECTION_CONFIDENCE): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_DIRECTION_CONFIDENCE), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_ABNORMALITY_EVIDENCE_COVERAGE): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_ABNORMALITY_EVIDENCE_COVERAGE), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_QUOTE_CONTEXT): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_QUOTE_CONTEXT), {}), separators=(",", ":")),
            names.field_name(OPTION_EVENT_DETAIL_SOURCE_REFS): json.dumps(detail.get(names.field_name(OPTION_EVENT_DETAIL_SOURCE_REFS), {}), separators=(",", ":")),
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
