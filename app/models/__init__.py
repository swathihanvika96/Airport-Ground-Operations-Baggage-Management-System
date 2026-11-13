"""Import every model so SQLAlchemy metadata (and Alembic autogenerate) sees all tables."""
from app.models.airport import Airport
from app.models.assignment import CounterAssignment, GateAssignment
from app.models.attendance import StaffAttendance
from app.models.audit_log import AuditLog
from app.models.baggage import Baggage
from app.models.baggage_screening import BaggageScreening
from app.models.baggage_tracking import BaggageTrackingEvent
from app.models.boarding_pass import BoardingPass
from app.models.checkin import CheckIn
from app.models.counter import CheckInCounter
from app.models.equipment import Equipment
from app.models.equipment_assignment import EquipmentAssignment
from app.models.equipment_maintenance import EquipmentMaintenance
from app.models.flight import Flight
from app.models.flight_delay import FlightDelay
from app.models.gate import Gate
from app.models.ground_staff import GroundStaff
from app.models.ground_task import GroundTask
from app.models.incident import Incident
from app.models.incident_history import IncidentHistory
from app.models.notification import Notification
from app.models.passenger import Passenger, PassengerFlight
from app.models.password_reset import PasswordResetToken
from app.models.resource_allocation import ResourceAllocation
from app.models.terminal import Terminal
from app.models.turnaround import Turnaround
from app.models.turnaround_activity import TurnaroundActivity
from app.models.user import User

__all__ = [
    "Airport", "AuditLog", "Baggage", "BaggageScreening", "BaggageTrackingEvent", "BoardingPass", "CheckIn",
    "CheckInCounter", "CounterAssignment", "Equipment", "EquipmentAssignment", "EquipmentMaintenance", "Flight",
    "FlightDelay", "Gate", "GateAssignment", "GroundStaff", "GroundTask", "Incident", "IncidentHistory",
    "Notification", "Passenger", "PassengerFlight", "PasswordResetToken", "ResourceAllocation", "StaffAttendance",
    "Terminal", "Turnaround", "TurnaroundActivity", "User",
]
