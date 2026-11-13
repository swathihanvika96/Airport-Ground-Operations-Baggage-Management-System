"""Datetime helpers. All datetimes are stored as naive UTC (MySQL DATETIME has no timezone)."""
from datetime import date, datetime, time, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def to_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def minutes_between(start: datetime | None, end: datetime | None) -> int | None:
    if not start or not end:
        return None
    return int(round((end - start).total_seconds() / 60))


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    end = datetime(year + (month // 12), (month % 12) + 1, 1)
    return start, end


def date_range_bounds(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    """Inclusive date range -> [start, end) datetimes."""
    start = datetime.combine(date_from, time.min) if date_from else None
    end = datetime.combine(date_to, time.min) + timedelta(days=1) if date_to else None
    return start, end
