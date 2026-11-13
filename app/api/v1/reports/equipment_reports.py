from fastapi import APIRouter, Depends

from app.api.dependencies import DB, allow
from app.api.v1.reports._common import ReportQuery, render
from app.core.permissions import Permissions
from app.models.user import User
from app.schemas.reports import ReportResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports/equipment", tags=["Reports"])


@router.get("/utilization", response_model=ReportResponse, responses={200: {"content": {"text/csv": {}}}},
            summary="Equipment utilisation report")
def utilization(db: DB, q: ReportQuery = Depends(), _: User = allow(Permissions.REPORTS_VIEW)):
    start, end = q.bounds
    rows, summary = ReportService(db).equipment_utilization(start, end, q.airport_id)
    return render("equipment_utilization", rows, summary, q, "hours_used", start, end)
