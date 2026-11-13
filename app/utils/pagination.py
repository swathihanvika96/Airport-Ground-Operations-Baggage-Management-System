"""Pagination helpers for SQLAlchemy 2.0 select statements and in-memory lists."""
import math
from dataclasses import dataclass
from typing import Any

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.constants import MAX_PAGE_SIZE


@dataclass
class PageParams:
    page: int = 1
    size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def page_params(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    size: int = Query(20, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
) -> PageParams:
    return PageParams(page=page, size=size)


def _page_dict(items: list[Any], total: int, params: PageParams) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "size": params.size,
        "pages": math.ceil(total / params.size) if params.size else 0,
    }


def paginate(db: Session, stmt: Select, params: PageParams) -> dict[str, Any]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = list(db.scalars(stmt.offset(params.offset).limit(params.size)).unique().all())
    return _page_dict(items, total, params)


def paginate_list(rows: list[Any], params: PageParams) -> dict[str, Any]:
    return _page_dict(rows[params.offset: params.offset + params.size], len(rows), params)
