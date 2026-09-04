"""Time helpers.

Everything in the app is timezone-aware UTC. ``utcnow()`` is the single source of
"now" so tests and seeds can reason about it consistently.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.core.errors import BadRequest

_MONTH_NAMES = (
    "янв",
    "фев",
    "мар",
    "апр",
    "май",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
)

PERIODS = ("all", "this_month", "last_month", "last_3_months", "custom")


def utcnow() -> datetime:
    """Timezone-aware current UTC time."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Attach UTC to a naive datetime, or convert an aware one to UTC.

    SQLite round-trips ``DateTime(timezone=True)`` columns as naive values, so every
    datetime read back out of the database goes through here.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def start_of_month(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def add_months(moment: datetime, months: int) -> datetime:
    """Shift a month-aligned datetime by ``months`` (may be negative)."""
    total = (moment.year * 12 + (moment.month - 1)) + months
    year, month = divmod(total, 12)
    return moment.replace(year=year, month=month + 1)


def resolve_period(
    period: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Turn a period name into a ``[start, end)`` UTC window.

    ``all`` resolves to ``(None, None)`` meaning "no filtering".
    """
    key = (period or "all").strip().lower()
    if key not in PERIODS:
        raise BadRequest("Неизвестный период")

    if key == "all":
        return None, None

    now = utcnow()
    this_month = start_of_month(now)

    if key == "this_month":
        return this_month, add_months(this_month, 1)
    if key == "last_month":
        return add_months(this_month, -1), this_month
    if key == "last_3_months":
        return add_months(this_month, -2), add_months(this_month, 1)

    # custom
    if date_from is None or date_to is None:
        raise BadRequest("Для своего периода укажите обе даты")
    if date_to < date_from:
        raise BadRequest("Дата окончания не может быть раньше даты начала")
    start = datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC)
    end = datetime(date_to.year, date_to.month, date_to.day, tzinfo=UTC) + timedelta(days=1)
    return start, end


def month_key(moment: datetime) -> str:
    """``2026-08`` for the month a datetime falls in."""
    moment = ensure_utc(moment)
    return f"{moment.year:04d}-{moment.month:02d}"


def month_label(key: str) -> str:
    """``2026-08`` -> ``авг 2026``."""
    year_str, _, month_str = key.partition("-")
    try:
        year = int(year_str)
        month = int(month_str)
    except ValueError:  # pragma: no cover - defensive
        return key
    if not 1 <= month <= 12:  # pragma: no cover - defensive
        return key
    return f"{_MONTH_NAMES[month - 1]} {year}"


def month_range(first: str, last: str) -> list[str]:
    """Every contiguous month key from ``first`` to ``last`` inclusive."""
    if not first or not last:
        return []
    start_year, start_month = (int(part) for part in first.split("-"))
    end_year, end_month = (int(part) for part in last.split("-"))
    start_index = start_year * 12 + (start_month - 1)
    end_index = end_year * 12 + (end_month - 1)
    if end_index < start_index:
        return []
    keys: list[str] = []
    for index in range(start_index, end_index + 1):
        year, month = divmod(index, 12)
        keys.append(f"{year:04d}-{month + 1:02d}")
    return keys


__all__ = [
    "PERIODS",
    "add_months",
    "ensure_utc",
    "month_key",
    "month_label",
    "month_range",
    "resolve_period",
    "start_of_month",
    "utcnow",
]
