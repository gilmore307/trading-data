"""Deterministic option-candidate feature builder for M05."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mid(row: Mapping[str, Any]) -> float | None:
    explicit = _float(row.get("mid"))
    if explicit is not None:
        return explicit
    bid = _float(row.get("bid"))
    ask = _float(row.get("ask"))
    if bid is not None and ask is not None:
        return (bid + ask) / 2
    return None


def _spread(row: Mapping[str, Any], mid: float | None) -> tuple[float | None, float | None]:
    explicit = _float(row.get("spread"))
    bid = _float(row.get("bid"))
    ask = _float(row.get("ask"))
    spread = explicit
    if spread is None and bid is not None and ask is not None:
        spread = ask - bid
    spread_pct = _float(row.get("spread_pct"))
    if spread_pct is None and spread is not None and mid not in (None, 0):
        spread_pct = spread / mid
    return spread, spread_pct


def _moneyness(row: Mapping[str, Any]) -> float | None:
    strike = _float(row.get("strike"))
    underlying_price = _float(row.get("underlying_price"))
    if strike in (None, 0) or underlying_price is None:
        return None
    right = str(row.get("option_right_type") or "").lower()
    if right == "put":
        return (strike / underlying_price) - 1
    return (underlying_price / strike) - 1


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    mid = _mid(row)
    spread, spread_pct = _spread(row, mid)
    bid_size = _float(row.get("bid_size"))
    ask_size = _float(row.get("ask_size"))
    return {
        "option_right_type": row.get("option_right_type"),
        "days_to_expiration": _float(row.get("days_to_expiration")),
        "strike": _float(row.get("strike")),
        "underlying_price": _float(row.get("underlying_price")),
        "moneyness": _moneyness(row),
        "bid": _float(row.get("bid")),
        "ask": _float(row.get("ask")),
        "mid": mid,
        "spread": spread,
        "spread_pct_mid": spread_pct,
        "bid_size": bid_size,
        "ask_size": ask_size,
        "quote_size_balance": None if bid_size is None or ask_size is None or (bid_size + ask_size) == 0 else (bid_size - ask_size) / (bid_size + ask_size),
        "implied_vol": _float(row.get("implied_vol")),
        "delta": _float(row.get("delta")),
        "theta": _float(row.get("theta")),
        "vega": _float(row.get("vega")),
        "rho": _float(row.get("rho")),
    }


def _quality(row: Mapping[str, Any]) -> dict[str, Any]:
    missing = [
        field
        for field in ("underlying", "snapshot_time", "snapshot_type", "option_symbol", "expiration", "option_right_type", "strike")
        if not row.get(field)
    ]
    has_quote = row.get("bid") is not None or row.get("ask") is not None or row.get("mid") is not None
    return {
        "missing_required_fields": missing,
        "has_required_fields": not missing,
        "has_quote": bool(has_quote),
        "has_iv": row.get("implied_vol") is not None,
        "has_first_order_greeks": any(row.get(field) is not None for field in ("delta", "theta", "vega", "rho")),
        "point_in_time_clock": "snapshot_time",
        "source_table": "option_chain_state_source",
    }


def generate_rows(rows: Iterable[Mapping[str, Any]], *, run_id: str = "m05_option_expression_feature_generation") -> list[dict[str, Any]]:
    """Return deterministic option-candidate feature rows for M05."""

    output: list[dict[str, Any]] = []
    for row in rows:
        required = (row.get("underlying"), row.get("snapshot_time"), row.get("snapshot_type"), row.get("option_symbol"))
        if not all(required):
            continue
        output.append(
            {
                "run_id": run_id,
                "source_run_ref": row.get("source_run_ref") or row.get("run_id") or "option_chain_state_source",
                "underlying": str(row.get("underlying")),
                "snapshot_time": row.get("snapshot_time"),
                "snapshot_type": str(row.get("snapshot_type")),
                "option_symbol": str(row.get("option_symbol")),
                "feature_payload_json": _payload(row),
                "feature_quality_diagnostics": _quality(row),
            }
        )
    return output
