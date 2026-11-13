from sqlalchemy.orm import Session

from app.core.constants import FLIGHT_CLOSED_STATUSES, FLIGHT_STATUS_TRANSITIONS
from app.core.exceptions import BusinessRuleError, ConflictError, InvalidTransitionError
from app.core.permissions import NOTIFY_BAGGAGE, NOTIFY_CHECKIN, NOTIFY_FLIGHT_OPS, NOTIFY_GATE
from app.models.flight import Flight
from app.models.user import User
from app.repositories.airport_repository import AirportRepository
from app.repositories.flight_repository import FlightRepository
from app.repositories.terminal_repository import TerminalRepository
from app.schemas.flight import FlightCreate, FlightUpdate
from app.services.audit_service import AuditService, snapshot
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import utcnow
from app.utils.enums import AirportStatus, AuditAction, FlightStatus, NotificationType, Severity

SCHEDULE_FIELDS = ["scheduled_departure", "scheduled_arrival", "estimated_departure", "departure_terminal_id",
                   "aircraft_type", "aircraft_registration", "seat_capacity", "airline_name"]


def validate_flight_transition(current: FlightStatus, target: FlightStatus) -> None:
    allowed = FLIGHT_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError("flight", current, target, allowed)


class FlightService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FlightRepository(db)
        self.airports = AirportRepository(db)
        self.terminals = TerminalRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def get(self, flight_id: int, lock: bool = False) -> Flight:
        return self.repo.get_or_404(flight_id, lock=lock)

    def _validate_terminal(self, terminal_id, departure_airport_id):
        if terminal_id is None:
            return
        terminal = self.terminals.get_or_404(terminal_id)
        if terminal.airport_id != departure_airport_id:
            raise BusinessRuleError("Departure terminal must belong to the departure airport")

    def create(self, data: FlightCreate, user: User) -> Flight:
        dep = self.airports.get_or_404(data.departure_airport_id)
        self.airports.get_or_404(data.arrival_airport_id)
        if dep.operational_status == AirportStatus.CLOSED:
            raise BusinessRuleError(f"Departure airport {dep.code} is closed")
        self._validate_terminal(data.departure_terminal_id, dep.id)
        if self.repo.exists(flight_number=data.flight_number, scheduled_departure=data.scheduled_departure):
            raise ConflictError(f"Flight {data.flight_number} already scheduled at {data.scheduled_departure}")
        flight = self.repo.create(**data.model_dump())
        self.audit.log(AuditAction.FLIGHT_CREATED, "flight", flight.id, None, snapshot(flight), user.id)
        self.db.commit()
        return flight

    def update(self, flight_id: int, data: FlightUpdate, user: User) -> Flight:
        flight = self.get(flight_id, lock=True)
        if flight.status in FLIGHT_CLOSED_STATUSES:
            raise BusinessRuleError(f"Cannot modify a flight that is {flight.status.value}")
        changes = data.model_dump(exclude_unset=True)
        dep = changes.get("scheduled_departure", flight.scheduled_departure)
        arr = changes.get("scheduled_arrival", flight.scheduled_arrival)
        if arr <= dep:
            raise BusinessRuleError("scheduled_arrival must be after scheduled_departure")
        if "departure_terminal_id" in changes:
            self._validate_terminal(changes["departure_terminal_id"], flight.departure_airport_id)
        prev = snapshot(flight, SCHEDULE_FIELDS)
        self.repo.update(flight, changes)
        self.audit.log(AuditAction.FLIGHT_SCHEDULE_CHANGED, "flight", flight.id, prev,
                       snapshot(flight, SCHEDULE_FIELDS), user.id)
        self.db.commit()
        return flight

    def update_status(self, flight_id: int, target: FlightStatus, user: User, actual_time=None,
                      remarks: str | None = None) -> Flight:
        flight = self.get(flight_id, lock=True)
        validate_flight_transition(flight.status, target)
        prev = snapshot(flight, ["status", "actual_departure", "actual_arrival"])
        now = actual_time or utcnow()
        if target == FlightStatus.DEPARTED:
            flight.actual_departure = now
            self._release_resources(flight, user)
        elif target == FlightStatus.ARRIVED:
            if flight.actual_departure and now < flight.actual_departure:
                raise BusinessRuleError("Arrival time cannot be before departure time")
            flight.actual_arrival = now
        elif target == FlightStatus.CANCELLED:
            self._release_resources(flight, user)
        flight.status = target
        self.audit.log(AuditAction.FLIGHT_STATUS_CHANGED, "flight", flight.id, prev,
                       {**snapshot(flight, ["status", "actual_departure", "actual_arrival"]), "remarks": remarks},
                       user.id)
        self._notify_status(flight, target)
        self.db.commit()
        return flight

    def _notify_status(self, flight: Flight, status: FlightStatus) -> None:
        fn = flight.flight_number
        if status == FlightStatus.BOARDING:
            gate = flight.gate_number or "TBA"
            self.notifications.notify_roles(NOTIFY_GATE, NotificationType.BOARDING_ANNOUNCEMENT,
                                            f"Boarding: {fn}", f"Flight {fn} is now boarding at gate {gate}.",
                                            "flight", flight.id, Severity.HIGH)
        elif status == FlightStatus.CANCELLED:
            self.notifications.notify_roles(NOTIFY_FLIGHT_OPS + NOTIFY_GATE + NOTIFY_CHECKIN + NOTIFY_BAGGAGE,
                                            NotificationType.FLIGHT_STATUS, f"Flight {fn} cancelled",
                                            f"Flight {fn} has been cancelled.", "flight", flight.id, Severity.HIGH)
        elif status == FlightStatus.CHECK_IN_OPEN:
            self.notifications.notify_roles(NOTIFY_CHECKIN, NotificationType.FLIGHT_STATUS,
                                            f"Check-in open: {fn}", f"Check-in is open for flight {fn}.",
                                            "flight", flight.id, Severity.LOW)

    def _release_resources(self, flight: Flight, user: User) -> None:
        """Free gate/counter/equipment/staff allocations once the flight departs or is cancelled."""
        from app.services.resource_service import ResourceService
        ResourceService(self.db).release_all_for_flight(flight, user)

    def delete(self, flight_id: int, user: User) -> None:
        from sqlalchemy import select
        from app.models.checkin import CheckIn
        flight = self.get(flight_id)
        if flight.status != FlightStatus.SCHEDULED:
            raise BusinessRuleError("Only SCHEDULED flights can be deleted; cancel it instead")
        if self.db.scalar(select(CheckIn.id).where(CheckIn.flight_id == flight.id).limit(1)):
            raise ConflictError("Flight has check-ins and cannot be deleted")
        self.audit.log(AuditAction.FLIGHT_DELETED, "flight", flight.id, snapshot(flight), None, user.id)
        self.repo.delete(flight)
        self.db.commit()
