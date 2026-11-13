from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.ground_task import GroundTask
from app.models.user import User
from app.repositories.task_repository import TaskRepository
from app.schemas.common import Page
from app.schemas.ground_task import TaskAssign, TaskCreate, TaskOut, TaskProgress, TaskUpdate
from app.services.task_service import TaskService
from app.utils.enums import Priority, TaskStatus, TaskType
from app.utils.filters import DateRangeParams, SortParams, apply_sorting
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/ground-tasks", tags=["Ground Tasks"])


@router.post("", response_model=TaskOut, status_code=201)
def create_task(data: TaskCreate, db: DB, user: User = allow(Permissions.TASK_MANAGE)):
    return TaskService(db).create(data, user)


@router.get("", response_model=Page[TaskOut])
def list_tasks(db: DB, _: CurrentUser, flight_id: int | None = None, staff_id: int | None = None,
               status: TaskStatus | None = None, priority: Priority | None = None,
               task_type: TaskType | None = None, dates: DateRangeParams = Depends(),
               params: PageParams = Depends(page_params), sort: SortParams = Depends()):
    start, end = dates.bounds
    stmt = TaskRepository(db).search(flight_id, staff_id, status, priority, task_type, start, end)
    stmt = apply_sorting(stmt, GroundTask, sort, default="created_at",
                         allowed={"created_at", "priority", "status", "scheduled_start", "due_time", "id"})
    return paginate(db, stmt, params)


@router.get("/my", response_model=Page[TaskOut], summary="Tasks assigned to the logged-in staff member")
def my_tasks(db: DB, user: CurrentUser, status: TaskStatus | None = None, params: PageParams = Depends(page_params)):
    return paginate(db, TaskService(db).my_tasks_stmt(user, status).order_by(GroundTask.id.desc()), params)


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: DB, _: CurrentUser):
    return TaskService(db).get(task_id)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskUpdate, db: DB, user: User = allow(Permissions.TASK_MANAGE)):
    return TaskService(db).update(task_id, data, user)


@router.post("/{task_id}/assign", response_model=TaskOut, summary="Assign / reassign (staff availability validated)")
def assign_task(task_id: int, data: TaskAssign, db: DB, user: User = allow(Permissions.TASK_MANAGE)):
    return TaskService(db).assign(task_id, data.staff_id, user)


@router.post("/{task_id}/start", response_model=TaskOut)
def start_task(task_id: int, data: TaskProgress, db: DB, user: User = allow(Permissions.TASK_EXECUTE)):
    return TaskService(db).start(task_id, user, data.remarks)


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: int, data: TaskProgress, db: DB, user: User = allow(Permissions.TASK_EXECUTE)):
    return TaskService(db).complete(task_id, user, data.remarks)


@router.post("/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: int, data: TaskProgress, db: DB, user: User = allow(Permissions.TASK_MANAGE)):
    return TaskService(db).cancel(task_id, user, data.remarks)
