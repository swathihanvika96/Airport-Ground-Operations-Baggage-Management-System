from sqlalchemy.orm import Session

from app.core.constants import TASK_STATUS_TRANSITIONS
from app.core.exceptions import BusinessRuleError, InvalidTransitionError
from app.core.permissions import NOTIFY_GROUND
from app.models.ground_task import GroundTask
from app.models.user import User
from app.repositories.flight_repository import FlightRepository
from app.repositories.staff_repository import StaffRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.turnaround_repository import TurnaroundRepository
from app.schemas.ground_task import TaskCreate, TaskUpdate
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.staff_service import ensure_staff_available
from app.utils.datetime_utils import utcnow
from app.utils.enums import AuditAction, FlightStatus, NotificationType, Priority, Severity, StaffAvailability, TaskStatus


def validate_task_transition(current: TaskStatus, target: TaskStatus) -> None:
    allowed = TASK_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError("task", current, target, allowed)


class TaskService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TaskRepository(db)
        self.flights = FlightRepository(db)
        self.staff = StaffRepository(db)
        self.turnarounds = TurnaroundRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def create(self, data: TaskCreate, user: User) -> GroundTask:
        flight = self.flights.get_or_404(data.flight_id)
        if flight.status in (FlightStatus.CANCELLED, FlightStatus.ARRIVED):
            raise BusinessRuleError(f"Cannot create tasks for a {flight.status.value} flight")
        if data.turnaround_activity_id and not self.turnarounds.get_activity(data.turnaround_activity_id):
            raise BusinessRuleError("Turnaround activity not found")
        if data.scheduled_start and data.due_time and data.due_time <= data.scheduled_start:
            raise BusinessRuleError("due_time must be after scheduled_start")
        task = self.repo.create(**data.model_dump(exclude={"assigned_staff_id"}), created_by_id=user.id,
                                status=TaskStatus.PENDING)
        if data.assigned_staff_id:
            self._assign(task, data.assigned_staff_id, user)
        self.db.commit()
        return task

    def get(self, task_id: int) -> GroundTask:
        return self.repo.get_or_404(task_id)

    def update(self, task_id: int, data: TaskUpdate, user: User) -> GroundTask:
        task = self.repo.get_or_404(task_id)
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise BusinessRuleError(f"Task is {task.status.value}")
        self.repo.update(task, data.model_dump(exclude_unset=True))
        self.db.commit()
        return task

    def _assign(self, task: GroundTask, staff_id: int, user: User) -> None:
        validate_task_transition(task.status, TaskStatus.ASSIGNED)
        staff = self.staff.get_or_404(staff_id, lock=True)
        ensure_staff_available(staff)
        prev = {"assigned_staff_id": task.assigned_staff_id, "status": task.status}
        task.assigned_staff_id = staff.id
        task.status = TaskStatus.ASSIGNED
        self.db.flush()
        self.audit.log(AuditAction.GROUND_TASK_ASSIGNED, "ground_task", task.id, prev,
                       {"assigned_staff_id": staff.id, "staff": staff.employee_code, "status": TaskStatus.ASSIGNED},
                       user.id)
        priority = Severity.HIGH if task.priority in (Priority.HIGH, Priority.CRITICAL) else Severity.MEDIUM
        title = f"Task assigned: {task.task_type.value.replace('_', ' ').title()}"
        message = (f"{staff.full_name} assigned to {task.task_type.value} for flight "
                   f"{task.flight.flight_number} (priority {task.priority.value}).")
        self.notifications.notify_roles(NOTIFY_GROUND, NotificationType.GROUND_TASK_ASSIGNMENT, title, message,
                                        "ground_task", task.id, priority,
                                        extra_user_ids=[staff.user_id] if staff.user_id else None)

    def assign(self, task_id: int, staff_id: int, user: User) -> GroundTask:
        task = self.repo.get_or_404(task_id)
        self._assign(task, staff_id, user)
        self.db.commit()
        return task

    def start(self, task_id: int, user: User, remarks: str | None = None) -> GroundTask:
        task = self.repo.get_or_404(task_id)
        validate_task_transition(task.status, TaskStatus.IN_PROGRESS)
        staff = self.staff.get_or_404(task.assigned_staff_id, lock=True)
        ensure_staff_available(staff)
        if self.repo.in_progress_for_staff(staff.id, exclude_task_id=task.id):
            raise BusinessRuleError(f"{staff.full_name} already has a task in progress", code="STAFF_BUSY")
        task.status = TaskStatus.IN_PROGRESS
        task.start_time = utcnow()
        if remarks:
            task.remarks = remarks
        staff.availability_status = StaffAvailability.ON_TASK
        self.audit.log(AuditAction.GROUND_TASK_UPDATED, "ground_task", task.id, {"status": "ASSIGNED"},
                       {"status": "IN_PROGRESS"}, user.id)
        self.db.commit()
        return task

    def complete(self, task_id: int, user: User, remarks: str | None = None) -> GroundTask:
        task = self.repo.get_or_404(task_id)
        validate_task_transition(task.status, TaskStatus.COMPLETED)
        task.status = TaskStatus.COMPLETED
        task.completion_time = utcnow()
        if remarks:
            task.remarks = remarks
        self._free_staff(task)
        self.audit.log(AuditAction.GROUND_TASK_UPDATED, "ground_task", task.id, {"status": "IN_PROGRESS"},
                       {"status": "COMPLETED", "remarks": remarks}, user.id)
        self.db.commit()
        return task

    def cancel(self, task_id: int, user: User, remarks: str | None = None) -> GroundTask:
        task = self.repo.get_or_404(task_id)
        validate_task_transition(task.status, TaskStatus.CANCELLED)
        prev = task.status
        task.status = TaskStatus.CANCELLED
        task.remarks = remarks or task.remarks
        if prev == TaskStatus.IN_PROGRESS:
            self._free_staff(task)
        self.audit.log(AuditAction.GROUND_TASK_UPDATED, "ground_task", task.id, {"status": prev},
                       {"status": "CANCELLED"}, user.id)
        self.db.commit()
        return task

    def _free_staff(self, task: GroundTask) -> None:
        if not task.assigned_staff_id:
            return
        staff = self.staff.get(task.assigned_staff_id)
        self.db.flush()
        if staff and staff.availability_status == StaffAvailability.ON_TASK and \
                not self.repo.in_progress_for_staff(staff.id, exclude_task_id=task.id):
            staff.availability_status = StaffAvailability.AVAILABLE

    def my_tasks_stmt(self, user: User, status=None):
        staff = self.staff.get_by(user_id=user.id)
        if not staff:
            raise BusinessRuleError("Your account is not linked to a ground staff profile")
        return self.repo.search(staff_id=staff.id, status=status)


