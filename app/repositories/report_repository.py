"""Read-only data access for reports."""
from sqlalchemy.orm import Session


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def rows(self, stmt):
        return self.db.execute(stmt).all()

    def scalars(self, stmt):
        return list(self.db.scalars(stmt).all())
