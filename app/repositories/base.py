"""Generic repository with common CRUD helpers (SQLAlchemy 2.0 style)."""
from datetime import datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.base import Base
from app.utils.enums import AssignmentStatus

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]
    entity_name: str = "Entity"

    def __init__(self, db: Session):
        self.db = db

    def get(self, entity_id: int) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def get_or_404(self, entity_id: int, lock: bool = False) -> ModelT:
        if lock:  # SELECT ... FOR UPDATE (honoured by MySQL/InnoDB) to serialise conflicting writes
            obj = self.db.scalar(select(self.model).where(self.model.id == entity_id).with_for_update())
        else:
            obj = self.get(entity_id)
        if obj is None:
            raise NotFoundError(self.entity_name, entity_id)
        return obj

    def get_by(self, **filters: Any) -> ModelT | None:
        return self.db.scalar(select(self.model).filter_by(**filters).limit(1))

    def exists(self, **filters: Any) -> bool:
        return self.get_by(**filters) is not None

    def query(self) -> Select:
        return select(self.model)

    def list(self, stmt: Select | None = None) -> list[ModelT]:
        return list(self.db.scalars(stmt if stmt is not None else self.query()).all())

    def count(self, stmt: Select | None = None) -> int:
        stmt = stmt if stmt is not None else self.query()
        return self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj

    def create(self, **data: Any) -> ModelT:
        return self.add(self.model(**data))

    def update(self, obj: ModelT, data: dict[str, Any]) -> ModelT:
        for key, value in data.items():
            setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()


def overlapping_active(model: Any, resource_col: Any, resource_id: int, start: datetime, end: datetime,
                       exclude_flight_id: int | None = None) -> Select:
    """Active assignments of a resource whose [start, end) window overlaps the given window."""
    stmt = select(model).where(
        resource_col == resource_id,
        model.status == AssignmentStatus.ACTIVE,
        model.start_time < end,
        model.end_time > start,
    )
    if exclude_flight_id is not None:
        stmt = stmt.where(model.flight_id != exclude_flight_id)
    return stmt
