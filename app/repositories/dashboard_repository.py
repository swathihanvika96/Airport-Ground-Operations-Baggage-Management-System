"""Aggregate queries for the operations dashboard."""
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db

    def count_by(self, column, stmt_filter: Select | None = None) -> dict:
        """Return {value: count} grouped by a column, optionally restricted by a base select's where-clause."""
        entity = column.class_
        stmt = select(column, func.count()).select_from(entity)
        if stmt_filter is not None and stmt_filter.whereclause is not None:
            stmt = stmt.where(stmt_filter.whereclause)
        stmt = stmt.group_by(column)
        return {k: v for k, v in self.db.execute(stmt).all()}

    def scalar(self, stmt):
        return self.db.scalar(stmt)
