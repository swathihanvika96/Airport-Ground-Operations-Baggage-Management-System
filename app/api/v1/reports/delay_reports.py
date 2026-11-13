from fastapi import APIRouter, Depends

from app.api.dependencies import DB, allow
from app.api.v1.reports._common import ReportQuery, render
from app.core.permissions import Permissions
from app.models.user import User
from app.schemas.reports import ReportResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports/delays", tags=["Reports"])


@router.get("/analysis", response_model=ReportResponse, responses={200: {"content": {"text/csv": {}}}},
            summary="Flight delay analysis by category")
def analysis(db: DB, q: ReportQuery = Depends(), _: User = allow(Permissions.REPORTS_VIEW)):
    start, end = q.bounds
    rows, summary = ReportService(db).delay_analysis(start, end, q.airport_id)
    return render("delay_analysis", rows, summary, q, "total_delay_minutes", start, end)
