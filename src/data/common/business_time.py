from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo('America/New_York')


def now_business() -> datetime:
    return datetime.now(UTC).astimezone(BUSINESS_TZ)


def business_now_iso() -> str:
    return now_business().isoformat()


def business_month_start(dt: datetime | None = None) -> datetime:
    local = (dt or now_business()).astimezone(BUSINESS_TZ)
    return datetime(local.year, local.month, 1, 0, 0, 0, tzinfo=BUSINESS_TZ)


def business_month_key(dt: datetime | None = None) -> str:
    local = (dt or now_business()).astimezone(BUSINESS_TZ)
    return f'{local.year:04d}-{local.month:02d}'
