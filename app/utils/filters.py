"""Reusable filtering / sorting helpers."""
from datetime import date, datetime
from typing import Any, Literal

from fastapi import Query
from sqlalchemy import Select, asc, desc

from app.core.exceptions import BusinessRuleError
from app.utils.datetime_utils import date_range_bounds

SortOrder = Literal["asc", "desc"]


class SortParams:
    def __init__(
        self,
        sort_by: str | None = Query(None, description="Field to sort by"),
        sort_order: SortOrder = Query("desc", description="asc | desc"),
    ):
        self.sort_by = sort_by
        self.sort_order = sort_order


class DateRangeParams:
    def __init__(
        self,
        date_from: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
        date_to: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    ):
        if date_from and date_to and date_from > date_to:
            raise BusinessRuleError("date_from must be before or equal to date_to")
        self.date_from = date_from
        self.date_to = date_to

    @property
    def bounds(self) -> tuple[datetime | None, datetime | None]:
        return date_range_bounds(self.date_from, self.date_to)


def apply_sorting(stmt: Select, model: Any, sort: SortParams | None, default: str = "id",
                  allowed: set[str] | None = None) -> Select:
    field = (sort.sort_by if sort and sort.sort_by else default)
    if allowed is not None and field not in allowed:
        raise BusinessRuleError(f"Cannot sort by '{field}'", details={"allowed": sorted(allowed)})
    column = getattr(model, field, None)
    if column is None:
        raise BusinessRuleError(f"Unknown sort field '{field}'")
    direction = desc if (sort is None or sort.sort_order == "desc") else asc
    return stmt.order_by(direction(column))


def apply_date_range(stmt: Select, column: Any, start: datetime | None, end: datetime | None) -> Select:
    if start is not None:
        stmt = stmt.where(column >= start)
    if end is not None:
        stmt = stmt.where(column < end)
    return stmt


def sort_rows(rows: list[dict[str, Any]], sort: SortParams | None, default: str | None = None) -> list[dict[str, Any]]:
    """Sort a list of dict rows (used by aggregated reports)."""
    if not rows:
        return rows
    field = (sort.sort_by if sort and sort.sort_by else default)
    if not field:
        return rows
    if field not in rows[0]:
        raise BusinessRuleError(f"Cannot sort by '{field}'", details={"allowed": sorted(rows[0].keys())})
    reverse = sort is None or sort.sort_order == "desc"
    # None values always last
    present = [r for r in rows if r.get(field) is not None]
    missing = [r for r in rows if r.get(field) is None]
    return sorted(present, key=lambda r: r[field], reverse=reverse) + missing
