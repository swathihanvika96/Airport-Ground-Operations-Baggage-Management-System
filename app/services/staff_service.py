from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError
from app.models.ground_staff import GroundStaff
from app.models.user import User
from app.repositories.staff_repository import StaffRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.ground_staff import StaffCreate, StaffUpdate
from app.utils.enums import StaffAvailability

UNAVAILABLE = {StaffAvailability.ON_LEAVE, StaffAvailability.OFF_DUTY}


def ensure_staff_available(staff: GroundStaff) -> None:
    """Shared staff availability validation (tasks, turnaround, resource allocation)."""
    if not staff.is_active:
        raise BusinessRuleError(f"Staff {staff.employee_code} is inactive", code="STAFF_UNAVAILABLE")
    if staff.availability_status in UNAVAILABLE:
        raise BusinessRuleError(f"Staff {staff.employee_code} is {staff.availability_status.value}",
                                code="STAFF_UNAVAILABLE")


class StaffService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = StaffRepository(db)
        self.users = UserRepository(db)
        self.tasks = TaskRepository(db)

    def _clean_skills(self, skills: list[str]) -> list[str]:
        return sorted({s.strip().lower() for s in skills if s and s.strip()})

    def create(self, data: StaffCreate, user: User) -> GroundStaff:
        code = data.employee_code.upper()
        if self.repo.exists(employee_code=code):
            raise ConflictError(f"Employee code {code} already exists")
        if data.supervisor_id:
            self.repo.get_or_404(data.supervisor_id)
        if data.user_id:
            self.users.get_or_404(data.user_id)
            if self.repo.exists(user_id=data.user_id):
                raise ConflictError("User account is already linked to another staff member")
        staff = self.repo.create(**data.model_dump(exclude={"employee_code", "skills"}), employee_code=code,
                                 skills=self._clean_skills(data.skills))
        self.db.commit()
        return staff

    def get(self, staff_id: int) -> GroundStaff:
        return self.repo.get_or_404(staff_id)

    def get_by_user(self, user_id: int) -> GroundStaff | None:
        return self.repo.get_by(user_id=user_id)

    def update(self, staff_id: int, data: StaffUpdate, user: User) -> GroundStaff:
        staff = self.repo.get_or_404(staff_id)
        changes = data.model_dump(exclude_unset=True)
        if "skills" in changes and changes["skills"] is not None:
            changes["skills"] = self._clean_skills(changes["skills"])
        sup = changes.get("supervisor_id")
        if sup:
            if sup == staff.id:
                raise BusinessRuleError("Staff cannot supervise themselves")
            self._check_no_cycle(staff.id, sup)
        self.repo.update(staff, changes)
        self.db.commit()
        return staff

    def _check_no_cycle(self, staff_id: int, supervisor_id: int) -> None:
        seen, current = set(), self.repo.get_or_404(supervisor_id)
        while current:
            if current.id == staff_id:
                raise BusinessRuleError("Supervisor assignment would create a reporting cycle")
            if current.id in seen:
                break
            seen.add(current.id)
            current = current.supervisor

    def set_availability(self, staff_id: int, status: StaffAvailability, user: User) -> GroundStaff:
        staff = self.repo.get_or_404(staff_id)
        if status in UNAVAILABLE and self.tasks.in_progress_for_staff(staff.id):
            raise BusinessRuleError("Staff has tasks in progress; complete or reassign them first")
        staff.availability_status = status
        self.db.commit()
        return staff

    def team(self, supervisor_id: int) -> list[GroundStaff]:
        self.repo.get_or_404(supervisor_id)
        return self.repo.list(self.repo.search(supervisor_id=supervisor_id))
