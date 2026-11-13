from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DB, allow
from app.api.v1.reports._common import ReportQuery, render
from app.core.permissions import Permissions
from app.models.user import User
from app.schemas.reports import ReportResponse
from app.services.report_service import ReportService
from app.utils.datetime_utils import day_bounds, month_bounds

router = APIRouter(prefix="/reports/flights", tags=["Reports"])
CSV = {"description": "JSON report, or a CSV file when format=csv",
       "content": {"text/csv": {}}}


@router.get("/daily", response_model=ReportResponse, responses={200: CSV}, summary="Daily flight operations report")
def daily(db: DB, q: ReportQuery = Depends(), _: User = allow(Permissions.REPORTS_VIEW),
          report_date: date | None = Query(None, description="Defaults to today; ignored if date_from/date_to set")):
    start, end = q.bounds
    if not (start or end):
        start, end = day_bounds(report_date or date.today())
    rows, summary = ReportService(db).daily_flight_operations(start, end, q.airport_id)
    return render("daily_flight_operations", rows, summary, q, "scheduled_departure", start, end)


@router.get("/monthly-performance", response_model=ReportResponse, responses={200: CSV},
            summary="Monthly flight performance by airline (OTP, delays, cancellations)")
def monthly(db: DB, q: ReportQuery = Depends(), _: User = allow(Permissions.REPORTS_VIEW),
            year: int | None = Query(None, ge=2000, le=2100), month: int | None = Query(None, ge=1, le=12)):
    start, end = q.bounds
    if year and month:
        start, end = month_bounds(year, month)
    elif not (start or end):
        today = date.today()
        start, end = month_bounds(today.year, today.month)
    rows, summary = ReportService(db).monthly_flight_performance(start, end, q.airport_id)
    return render("monthly_flight_performance", rows, summary, q, "total_flights", start, end)
