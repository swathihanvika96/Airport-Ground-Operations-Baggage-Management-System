from sqlalchemy import String, cast, or_, select

from app.models.ground_staff import GroundStaff
from app.repositories.base import BaseRepository


class StaffRepository(BaseRepository[GroundStaff]):
    model = GroundStaff
    entity_name = "Ground staff"

    def search(self, q=None, department=None, shift=None, availability=None, skill=None, supervisor_id=None,
               is_active=None):
        stmt = select(GroundStaff)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(GroundStaff.full_name.ilike(like), GroundStaff.employee_code.ilike(like),
                                  GroundStaff.designation.ilike(like)))
        if department:
            stmt = stmt.where(GroundStaff.department == department)
        if shift:
            stmt = stmt.where(GroundStaff.shift == shift)
        if availability:
            stmt = stmt.where(GroundStaff.availability_status == availability)
        if skill:
            stmt = stmt.where(cast(GroundStaff.skills, String).ilike(f'%"{skill}"%'))
        if supervisor_id:
            stmt = stmt.where(GroundStaff.supervisor_id == supervisor_id)
        if is_active is not None:
            stmt = stmt.where(GroundStaff.is_active.is_(is_active))
        return stmt
