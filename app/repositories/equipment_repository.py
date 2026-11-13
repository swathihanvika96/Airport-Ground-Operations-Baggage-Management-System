from sqlalchemy import or_, select

from app.models.equipment import Equipment
from app.models.equipment_assignment import EquipmentAssignment
from app.models.equipment_maintenance import EquipmentMaintenance
from app.repositories.base import BaseRepository, overlapping_active


class EquipmentRepository(BaseRepository[Equipment]):
    model = Equipment
    entity_name = "Equipment"

    def search(self, q=None, equipment_type=None, status=None, terminal_id=None, airport_id=None):
        stmt = select(Equipment)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Equipment.name.ilike(like), Equipment.equipment_code.ilike(like)))
        if equipment_type:
            stmt = stmt.where(Equipment.equipment_type == equipment_type)
        if status:
            stmt = stmt.where(Equipment.status == status)
        if terminal_id:
            stmt = stmt.where(Equipment.terminal_id == terminal_id)
        if airport_id:
            stmt = stmt.where(Equipment.airport_id == airport_id)
        return stmt

    def conflicts(self, equipment_id, start, end):
        return list(self.db.scalars(overlapping_active(
            EquipmentAssignment, EquipmentAssignment.equipment_id, equipment_id, start, end)).all())

    def get_assignment(self, assignment_id) -> EquipmentAssignment | None:
        return self.db.get(EquipmentAssignment, assignment_id)

    def assignments(self, equipment_id=None, flight_id=None, status=None):
        stmt = select(EquipmentAssignment)
        if equipment_id:
            stmt = stmt.where(EquipmentAssignment.equipment_id == equipment_id)
        if flight_id:
            stmt = stmt.where(EquipmentAssignment.flight_id == flight_id)
        if status:
            stmt = stmt.where(EquipmentAssignment.status == status)
        return stmt.order_by(EquipmentAssignment.created_at.desc(), EquipmentAssignment.id.desc())

    def get_maintenance(self, maintenance_id) -> EquipmentMaintenance | None:
        return self.db.get(EquipmentMaintenance, maintenance_id)

    def maintenance(self, equipment_id=None, status=None):
        stmt = select(EquipmentMaintenance)
        if equipment_id:
            stmt = stmt.where(EquipmentMaintenance.equipment_id == equipment_id)
        if status:
            stmt = stmt.where(EquipmentMaintenance.status == status)
        return stmt.order_by(EquipmentMaintenance.scheduled_date.desc())
