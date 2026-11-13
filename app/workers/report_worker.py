"""Background CSV report generation (FastAPI BackgroundTasks; swap for Celery/RQ with Redis if needed)."""
import logging
import os
from datetime import datetime

from app.core.config import settings
from app.db.session import SessionLocal
from app.utils.csv_export import rows_to_csv

logger = logging.getLogger("workers.reports")


def generate_report_file(report_name: str, start: datetime | None, end: datetime | None,
                         airport_id: int | None = None) -> str:
    from app.services.report_service import ReportService
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    db = SessionLocal()
    try:
        rows, _ = getattr(ReportService(db), report_name)(start, end, airport_id)
        path = os.path.join(settings.REPORTS_DIR, f"{report_name}_{datetime.utcnow():%Y%m%d_%H%M%S}.csv")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(rows_to_csv(rows))
        logger.info("Report %s written to %s (%d rows)", report_name, path, len(rows))
        return path
    finally:
        db.close()
