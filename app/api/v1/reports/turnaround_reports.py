from fastapi import APIRouter, Depends

from app.api.dependencies import DB, allow
from app.api.v1.reports._common import ReportQuery, render
from app.core.permissions import Permissions
from app.models.user import User
from app.schemas.reports import ReportResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports/turnarounds", tags=["Reports"])


@router.get("", response_model=ReportResponse, responses={200: {"content": {"text/csv": {}}}},
            summary="Aircraft turnaround report")
def turnaround(db: DB, q: ReportQuery = Depends(), _: User = allow(Permissions.REPORTS_VIEW)):
    start, end = q.bounds
    rows, summary = ReportService(db).turnaround_report(start, end, q.airport_id)
    return render("turnaround_report", rows, summary, q, "turnaround_id", start, end)
