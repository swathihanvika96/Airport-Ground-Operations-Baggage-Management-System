from typing import Any

from pydantic import BaseModel


class ReportResponse(BaseModel):
    report: str
    filters: dict[str, Any]
    summary: dict[str, Any] = {}
    items: list[dict[str, Any]]
    total: int
    page: int
    size: int
    pages: int
