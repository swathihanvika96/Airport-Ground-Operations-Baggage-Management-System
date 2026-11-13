from sqlalchemy import select

from app.models.ground_task import GroundTask
from app.repositories.base import BaseRepository
from app.utils.enums import TaskStatus


class TaskRepository(BaseRepository[GroundTask]):
    model = GroundTask
    entity_name = "Ground task"

    def search(self, flight_id=None, staff_id=None, status=None, priority=None, task_type=None, start=None, end=None):
        stmt = select(GroundTask)
        if flight_id:
            stmt = stmt.where(GroundTask.flight_id == flight_id)
        if staff_id:
            stmt = stmt.where(GroundTask.assigned_staff_id == staff_id)
        if status:
            stmt = stmt.where(GroundTask.status == status)
        if priority:
            stmt = stmt.where(GroundTask.priority == priority)
        if task_type:
            stmt = stmt.where(GroundTask.task_type == task_type)
        if start:
            stmt = stmt.where(GroundTask.created_at >= start)
        if end:
            stmt = stmt.where(GroundTask.created_at < end)
        return stmt

    def in_progress_for_staff(self, staff_id, exclude_task_id=None) -> list[GroundTask]:
        stmt = select(GroundTask).where(GroundTask.assigned_staff_id == staff_id,
                                        GroundTask.status == TaskStatus.IN_PROGRESS)
        if exclude_task_id:
            stmt = stmt.where(GroundTask.id != exclude_task_id)
        return list(self.db.scalars(stmt).all())
