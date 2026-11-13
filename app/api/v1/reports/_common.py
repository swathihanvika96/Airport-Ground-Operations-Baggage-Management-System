"""Shared plumbing for report endpoints: date range, sorting, pagination and CSV export."""
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.api.dependencies import allow
from app.core.exceptions import BusinessRuleError
from app.core.permissions import Permissions
from app.models.user import User
from app.utils.csv_export import csv_response
from app.utils.filters import DateRangeParams, SortParams, sort_rows
from app.utils.pagination import PageParams, page_params, paginate_list

ReportFormat = Literal["json", "csv"]
REPORT_NAMES = {
    "daily_flight_operations", "monthly_flight_performance", "baggage_handling", "missing_baggage",
    "staff_performance", "equipment_utilization", "delay_analysis", "turnaround_report",
}


class ReportQuery:
    def __init__(self, dates: DateRangeParams = Depends(), params: PageParams = Depends(page_params),
                 sort: SortParams = Depends(), airport_id: int | None = Query(None),
                 format: ReportFormat = Query("json", description="json | csv")):
        self.dates, self.params, self.sort, self.airport_id, self.format = dates, params, sort, airport_id, format

    @property
    def bounds(self):
        return self.dates.bounds


def render(name: str, rows: list[dict], summary: dict, q: ReportQuery, default_sort: str | None = None,
           start: datetime | None = None, end: datetime | None = None):
    rows = sort_rows(rows, q.sort, default_sort)
    if q.format == "csv":
        return csv_response(rows, f"{name}_{date.today():%Y%m%d}.csv")
    page = paginate_list(rows, q.params)
    filters = {"date_from": q.dates.date_from, "date_to": q.dates.date_to, "airport_id": q.airport_id,
               "period_start": start, "period_end": end, "sort_by": q.sort.sort_by, "sort_order": q.sort.sort_order}
    return {"report": name, "filters": filters, "summary": summary, **page}


export_router = APIRouter(prefix="/reports", tags=["Reports"])


@export_router.post("/{report_name}/export-async", summary="Generate a CSV report in the background")
def export_async(report_name: str, background: BackgroundTasks, q: ReportQuery = Depends(),
                 _: User = allow(Permissions.REPORTS_VIEW)):
    if report_name not in REPORT_NAMES:
        raise BusinessRuleError("Unknown report", details={"available": sorted(REPORT_NAMES)})
    from app.workers.report_worker import generate_report_file
    start, end = q.bounds
    background.add_task(generate_report_file, report_name, start, end, q.airport_id)
    return {"message": f"Report '{report_name}' is being generated", "status": "queued"}
