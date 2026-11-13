from fastapi import APIRouter, Depends

from app.api.dependencies import DB, allow
from app.api.v1.reports._common import ReportQuery, render
from app.core.permissions import Permissions
from app.models.user import User
from app.schemas.reports import ReportResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports/baggage", tags=["Reports"])
CSV = {"content": {"text/csv": {}}}


@router.get("/handling", response_model=ReportResponse, responses={200: CSV}, summary="Baggage handling report")
def handling(db: DB, q: ReportQuery = Depends(), _: User = allow(Permissions.REPORTS_VIEW)):
    start, end = q.bounds
    rows, summary = ReportService(db).baggage_handling(start, end, q.airport_id)
    return render("baggage_handling", rows, summary, q, "scheduled_departure", start, end)


@router.get("/missing", response_model=ReportResponse, responses={200: CSV}, summary="Missing baggage report")
def missing(db: DB, q: ReportQuery = Depends(), _: User = allow(Permissions.REPORTS_VIEW)):
    start, end = q.bounds
    rows, summary = ReportService(db).missing_baggage(start, end, q.airport_id)
    return render("missing_baggage", rows, summary, q, "reported_missing_at", start, end)
