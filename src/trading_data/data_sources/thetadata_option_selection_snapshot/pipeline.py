"""ThetaData option-chain selection snapshot acquisition bundle.

Development-stage output is a single final ``option_chain_snapshot.csv`` file.
Raw provider responses are fetched and normalized in memory, then discarded.
"""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from trading_data.source_availability.http import HttpClient, HttpResult
from trading_data.source_availability.sanitize import sanitize_url, sanitize_value
from trading_data.source_availability.secrets import load_secret_alias, public_secret_summary

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
DEFAULT_REGISTRY_CSV = Path("/root/projects/trading-main/registry/current.csv")
BUNDLE = "thetadata_option_selection_snapshot"


@dataclass(frozen=True)
class BundleContext:
    task_key: dict[str, Any]
    run_dir: Path
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
    "fld_OPT015": "open",
    "fld_OPT016": "high",
    "fld_OPT017": "low",
    "fld_OPT018": "close",
    "fld_OPT019": "volume",
    "fld_OPT020": "trade_count",
    "fld_OPT021": "vwap",
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
class FetchedSnapshot:
    underlying: str
    snapshot_time: datetime
    quote_rows: list[dict[str, Any]]
    iv_rows: list[dict[str, Any]]
    greeks_rows: list[dict[str, Any]]
    request_evidence: list[dict[str, Any]]
    secret_alias: dict[str, Any] | None


class ThetaDataOptionSelectionSnapshotError(ValueError):
    pass


class RegistryNames:
    """Resolve retained registry fields and retired local-output field names."""

    def __init__(self, registry_csv: Path = DEFAULT_REGISTRY_CSV) -> None:
        with registry_csv.open(newline="", encoding="utf-8") as handle:
            import csv

            self._rows = {row["id"]: row for row in csv.DictReader(handle)}

    def payload(self, ref: RegistryRef) -> str:
        row = self._rows.get(ref.id)
        if row is None:
            try:
                return RETIRED_LOCAL_FIELD_PAYLOADS[ref.id]
            except KeyError as exc:
                raise ThetaDataOptionSelectionSnapshotError(f"registry id not found: {ref.id}") from exc
        if row["kind"] not in ref.expected_kinds:
            raise ThetaDataOptionSelectionSnapshotError(
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
SNAPSHOT_TIME = field("fld_OPT005")
OPTION_CONTRACT_COUNT = field("fld_OPT006")
OPTION_CONTRACTS = field("fld_OPT007")
OPTION_QUOTE_CONTEXT = field("fld_OPT008")
IV_CONTEXT = field("fld_OPT009")
GREEKS_CONTEXT = field("fld_OPT010")
OPTION_UNDERLYING_CONTEXT = field("fld_OPT011")
DERIVED_CONTEXT = field("fld_OPT012")
DATA_TIMESTAMP = field("fld_OPT013")
QUOTE_BID = field("fld_OPT032")
QUOTE_ASK = field("fld_OPT033")
QUOTE_MID = field("fld_OPT034")
QUOTE_SPREAD = field("fld_OPT035")
QUOTE_SPREAD_PCT = field("fld_OPT036")
QUOTE_BID_SIZE = field("fld_OPT037")
QUOTE_ASK_SIZE = field("fld_OPT038")
IMPLIED_VOL = field("fld_OPT045")
GREEK_DELTA = field("fld_OPT051")
GREEK_THETA = field("fld_OPT052")
GREEK_VEGA = field("fld_OPT053")
GREEK_RHO = field("fld_OPT054")
GREEK_EPSILON = field("fld_OPT055")
GREEK_LAMBDA = field("fld_OPT056")
UNDERLYING_PRICE = field("fld_OPT057")
UNDERLYING_TIMESTAMP = field("fld_OPT058")
OPTION_DAYS_TO_EXPIRATION = field("fld_OPT059")
QUOTE_BID_EXCHANGE = field("fld_OPT060")
QUOTE_ASK_EXCHANGE = field("fld_OPT061")
QUOTE_BID_CONDITION = field("fld_OPT062")
QUOTE_ASK_CONDITION = field("fld_OPT063")
IV_ERROR = field("fld_OPT064")
OPTION_CHAIN_SNAPSHOT = data_kind("dki_OPCHAIN1")


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", []):
        raise ThetaDataOptionSelectionSnapshotError(f"{BUNDLE}.params.{key} is required")
    return value


def _parse_snapshot_time(value: Any) -> datetime:
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ThetaDataOptionSelectionSnapshotError(
            f"{BUNDLE}.params.snapshot_time must be an ISO datetime"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ET)
    return parsed.astimezone(ET)


def _parse_thetadata_timestamp(value: Any, *, naive_tz: timezone | ZoneInfo = ET) -> str | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=naive_tz)
    return parsed.astimezone(ET).isoformat()


def _ms_since_midnight_et(value: datetime) -> str:
    midnight = value.replace(hour=0, minute=0, second=0, microsecond=0)
    delta = value - midnight
    return str(int(delta.total_seconds() * 1000))


def _json_response(result: HttpResult) -> Any:
    if result.status is None:
        raise ThetaDataOptionSelectionSnapshotError(
            f"request failed before HTTP response: {result.error_type}: {result.error_message}"
        )
    if result.status < 200 or result.status >= 300:
        raise ThetaDataOptionSelectionSnapshotError(
            f"request returned HTTP {result.status}: {result.error_message or result.text()[:240]}"
        )
    try:
        return result.json()
    except json.JSONDecodeError as exc:
        raise ThetaDataOptionSelectionSnapshotError("ThetaData response was not JSON") from exc


def _response_rows(payload: Any, endpoint_name: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("response"), list):
        raise ThetaDataOptionSelectionSnapshotError(f"ThetaData {endpoint_name} response was not a list")
    rows = payload["response"]
    if not all(isinstance(row, dict) for row in rows):
        raise ThetaDataOptionSelectionSnapshotError(f"ThetaData {endpoint_name} rows were not objects")
    return rows


def build_context(task_key: dict[str, Any], run_id: str) -> BundleContext:
    if task_key.get("bundle") != BUNDLE:
        raise ThetaDataOptionSelectionSnapshotError(f"task_key.bundle must be {BUNDLE}")
    root = Path(str(task_key.get("output_root") or f"storage/{task_key.get('task_id', BUNDLE + '_task')}"))
    run_dir = root / "runs" / run_id
    registry_csv = Path(str((task_key.get("params") or {}).get("registry_csv") or DEFAULT_REGISTRY_CSV))
    return BundleContext(
        task_key=task_key,
        run_dir=run_dir,
        saved_dir=run_dir / "saved",
        receipt_path=root / "completion_receipt.json",
        registry_csv=registry_csv,
        metadata={"run_id": run_id, "started_at": _now_utc()},
    )


def _fetch_endpoint(
    client: HttpClient,
    base_url: str,
    endpoint: str,
    params: Mapping[str, str],
    name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = client.get(f"{base_url}{endpoint}", params=dict(params), headers={"Accept": "application/json"})
    payload = _json_response(result)
    rows = _response_rows(payload, name)
    return rows, {
        "endpoint": sanitize_url(result.url),
        "http_status": result.status,
        "row_count": len(rows),
    }


def fetch(context: BundleContext, *, client: HttpClient | None = None) -> tuple[StepResult, FetchedSnapshot]:
    params = dict(context.task_key.get("params") or {})
    underlying = str(_required(params, "underlying")).upper()
    snapshot_time = _parse_snapshot_time(_required(params, "snapshot_time"))
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
        "expiration": "*",
        "date": snapshot_time.date().isoformat(),
        "ms_of_day": _ms_since_midnight_et(snapshot_time),
        "format": "json",
    }
    quote_rows, quote_evidence = _fetch_endpoint(
        client, base_url, "/v3/option/snapshot/quote", request_params, "quote snapshot"
    )
    iv_rows, iv_evidence = _fetch_endpoint(
        client,
        base_url,
        "/v3/option/snapshot/greeks/implied_volatility",
        request_params,
        "implied-volatility snapshot",
    )
    greeks_rows, greeks_evidence = _fetch_endpoint(
        client,
        base_url,
        "/v3/option/snapshot/greeks/first_order",
        request_params,
        "first-order Greeks snapshot",
    )

    context.run_dir.mkdir(parents=True, exist_ok=True)
    manifest = context.run_dir / "request_manifest.json"
    evidence = [quote_evidence, iv_evidence, greeks_evidence]
    manifest.write_text(
        json.dumps(
            {
                "bundle": BUNDLE,
                "underlying": underlying,
                "snapshot_time": snapshot_time.isoformat(),
                "params": sanitize_value(request_params),
                "requests": evidence,
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
        {
            "quote_snapshot_rows_transient": len(quote_rows),
            "iv_snapshot_rows_transient": len(iv_rows),
            "greeks_snapshot_rows_transient": len(greeks_rows),
        },
        details={"underlying": underlying, "snapshot_time": snapshot_time.isoformat()},
    ), FetchedSnapshot(
        underlying=underlying,
        snapshot_time=snapshot_time,
        quote_rows=quote_rows,
        iv_rows=iv_rows,
        greeks_rows=greeks_rows,
        request_evidence=evidence,
        secret_alias=secret_summary,
    )


def _contract_key(row: Mapping[str, Any]) -> tuple[str, str, float, str] | None:
    contract = row.get("contract")
    if not isinstance(contract, Mapping):
        return None
    symbol = str(contract.get("symbol") or "").upper()
    expiration = str(contract.get("expiration") or "")
    right = str(contract.get("right") or "").upper()
    strike = contract.get("strike")
    if not symbol or not expiration or not right or strike in (None, ""):
        return None
    return symbol, expiration, float(strike), right


def _first_data(row: Mapping[str, Any]) -> dict[str, Any]:
    data = row.get("data")
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes)) and data:
        first = data[0]
        return dict(first) if isinstance(first, Mapping) else {}
    return {}


def _index_rows(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, float, str], dict[str, Any]]:
    indexed: dict[tuple[str, str, float, str], dict[str, Any]] = {}
    for row in rows:
        key = _contract_key(row)
        if key is None:
            continue
        indexed[key] = _first_data(row)
    return indexed


def _number(value: Any) -> float | int | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed.is_integer():
        return int(parsed)
    return parsed


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compact(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


def _days_to_expiration(expiration: str, snapshot_date: date) -> int | None:
    try:
        expiration_date = date.fromisoformat(expiration)
    except ValueError:
        return None
    return (expiration_date - snapshot_date).days


def _right_sort_value(right: str) -> int:
    return {"CALL": 0, "PUT": 1}.get(right.upper(), 2)


def clean(context: BundleContext, fetched: FetchedSnapshot) -> tuple[StepResult, dict[str, Any]]:
    names = RegistryNames(context.registry_csv)
    f = names.payload
    quote_index = _index_rows(fetched.quote_rows)
    iv_index = _index_rows(fetched.iv_rows)
    greeks_index = _index_rows(fetched.greeks_rows)
    keys = sorted(
        set(quote_index) | set(iv_index) | set(greeks_index),
        key=lambda key: (key[1], key[2], _right_sort_value(key[3]), key[0]),
    )

    contracts: list[dict[str, Any]] = []
    warnings: list[str] = []
    for symbol, expiration, strike, right in keys:
        days_to_expiration = _days_to_expiration(expiration, fetched.snapshot_time.date())
        if days_to_expiration is not None and days_to_expiration < 0:
            continue
        quote = quote_index.get((symbol, expiration, strike, right), {})
        iv = iv_index.get((symbol, expiration, strike, right), {})
        greeks = greeks_index.get((symbol, expiration, strike, right), {})

        bid = _float(quote.get("bid"))
        ask = _float(quote.get("ask"))
        mid = (bid + ask) / 2 if bid is not None and ask is not None else None
        spread = ask - bid if bid is not None and ask is not None else None
        spread_pct = spread / mid if spread is not None and mid not in (None, 0) else None

        source_for_underlying = greeks or iv
        contract = {
            f(OPTION_EXPIRATION): expiration,
            f(OPTION_RIGHT_TYPE): right,
            f(OPTION_STRIKE): strike,
            f(OPTION_QUOTE_CONTEXT): _compact(
                {
                    f(DATA_TIMESTAMP): _parse_thetadata_timestamp(quote.get("timestamp")),
                    f(QUOTE_BID): bid,
                    f(QUOTE_ASK): ask,
                    f(QUOTE_MID): mid,
                    f(QUOTE_SPREAD): spread,
                    f(QUOTE_SPREAD_PCT): spread_pct,
                    f(QUOTE_BID_SIZE): _number(quote.get("bid_size")),
                    f(QUOTE_ASK_SIZE): _number(quote.get("ask_size")),
                    f(QUOTE_BID_EXCHANGE): _number(quote.get("bid_exchange")),
                    f(QUOTE_ASK_EXCHANGE): _number(quote.get("ask_exchange")),
                    f(QUOTE_BID_CONDITION): _number(quote.get("bid_condition")),
                    f(QUOTE_ASK_CONDITION): _number(quote.get("ask_condition")),
                }
            ),
            f(IV_CONTEXT): _compact(
                {
                    f(DATA_TIMESTAMP): _parse_thetadata_timestamp(iv.get("timestamp")),
                    f(IMPLIED_VOL): _float(iv.get("implied_vol")),
                    f(IV_ERROR): _float(iv.get("iv_error")),
                }
            ),
            f(GREEKS_CONTEXT): _compact(
                {
                    f(DATA_TIMESTAMP): _parse_thetadata_timestamp(greeks.get("timestamp")),
                    f(GREEK_DELTA): _float(greeks.get("delta")),
                    f(GREEK_THETA): _float(greeks.get("theta")),
                    f(GREEK_VEGA): _float(greeks.get("vega")),
                    f(GREEK_RHO): _float(greeks.get("rho")),
                    f(GREEK_EPSILON): _float(greeks.get("epsilon")),
                    f(GREEK_LAMBDA): _float(greeks.get("lambda")),
                }
            ),
            f(DERIVED_CONTEXT): _compact({f(OPTION_DAYS_TO_EXPIRATION): days_to_expiration}),
            f(OPTION_UNDERLYING_CONTEXT): _compact(
                {
                    f(UNDERLYING_PRICE): _float(source_for_underlying.get("underlying_price")),
                    f(UNDERLYING_TIMESTAMP): _parse_thetadata_timestamp(
                        source_for_underlying.get("underlying_timestamp"), naive_tz=UTC
                    ),
                }
            ),
        }
        contracts.append(contract)

    if len(quote_index) != len(keys):
        warnings.append("some contracts were present only in IV/Greeks snapshots and have empty quote context")
    if not contracts:
        raise ThetaDataOptionSelectionSnapshotError("ThetaData snapshot returned no contracts after normalization")

    snapshot = {
        f(OPTION_UNDERLYING): fetched.underlying,
        f(SNAPSHOT_TIME): fetched.snapshot_time.isoformat(),
        f(OPTION_CONTRACT_COUNT): len(contracts),
        f(OPTION_CONTRACTS): contracts,
    }
    return StepResult(
        "succeeded",
        [],
        {"option_chain_snapshot": 1, "option_chain_snapshot_contracts": len(contracts)},
        warnings=warnings,
        details={"contract_count": len(contracts), "format": "csv"},
    ), snapshot


def save(context: BundleContext, clean_result: StepResult, snapshot: dict[str, Any]) -> StepResult:
    names = RegistryNames(context.registry_csv)
    fields = [
        names.payload(OPTION_UNDERLYING),
        names.payload(SNAPSHOT_TIME),
        names.payload(OPTION_CONTRACT_COUNT),
        names.payload(OPTION_CONTRACTS),
    ]
    row = dict(snapshot)
    row[names.payload(OPTION_CONTRACTS)] = json.dumps(row.get(names.payload(OPTION_CONTRACTS), []), separators=(",", ":"))
    context.saved_dir.mkdir(parents=True, exist_ok=True)
    path = context.saved_dir / "option_chain_snapshot.csv"
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerow(row)
    os.replace(tmp_path, path)
    return StepResult(
        "succeeded",
        [str(path)],
        dict(clean_result.row_counts),
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
    entry = {
        "run_id": context.metadata["run_id"],
        "status": status,
        "started_at": context.metadata.get("started_at"),
        "completed_at": _now_utc(),
        "output_dir": str(context.run_dir),
        "outputs": outputs,
        "row_counts": row_counts,
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
        details={"run_id": context.metadata["run_id"], "error": entry["error"]},
    )


def run(task_key: dict[str, Any], *, run_id: str, client: HttpClient | None = None) -> StepResult:
    context = build_context(task_key, run_id)
    fetch_result = clean_result = save_result = None
    try:
        fetch_result, fetched = fetch(context, client=client)
        clean_result, snapshot = clean(context, fetched)
        save_result = save(context, clean_result, snapshot)
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
