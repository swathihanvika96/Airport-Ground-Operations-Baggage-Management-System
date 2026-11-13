"""Airport operations dashboard metrics."""
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.baggage import Baggage
from app.models.counter import CheckInCounter
from app.models.equipment import Equipment
from app.models.flight import Flight
from app.models.flight_delay import FlightDelay
from app.models.gate import Gate
from app.models.ground_staff import GroundStaff
from app.models.ground_task import GroundTask
from app.models.incident import Incident
from app.models.terminal import Terminal
from app.models.turnaround import Turnaround
from app.repositories.dashboard_repository import DashboardRepository
from app.utils.datetime_utils import date_range_bounds
from app.utils.enums import (
    BaggageStatus,
    CounterStatus,
    EquipmentStatus,
    FlightStatus,
    GateStatus,
    IncidentStatus,
    Severity,
    StaffAvailability,
    TaskStatus,
    TurnaroundStatus,
)

ON_TIME_THRESHOLD_MIN = 15


def on_time_performance(flights: list[tuple]) -> float | None:
    """flights: (scheduled_departure, actual_departure) of departed flights -> % departing within 15 min."""
    if not flights:
        return None
    on_time = sum(1 for sched, actual in flights
                  if actual is not None and (actual - sched).total_seconds() <= ON_TIME_THRESHOLD_MIN * 60)
    return round(100.0 * on_time / len(flights), 2)


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DashboardRepository(db)

    def overview(self, date_from: date | None = None, date_to: date | None = None,
                 airport_id: int | None = None) -> dict:
        start, end = date_range_bounds(date_from, date_to)

        # ---- flights (by scheduled departure in range) ----
        fstmt = select(Flight)
        if start:
            fstmt = fstmt.where(Flight.scheduled_departure >= start)
        if end:
            fstmt = fstmt.where(Flight.scheduled_departure < end)
        if airport_id:
            fstmt = fstmt.where(or_(Flight.departure_airport_id == airport_id, Flight.arrival_airport_id == airport_id))
        flight_ids = select(Flight.id).where(fstmt.whereclause) if fstmt.whereclause is not None else select(Flight.id)
        by_status = self.repo.count_by(Flight.status, fstmt)
        g = lambda s: by_status.get(s, 0)  # noqa: E731
        departed_rows = self.db.execute(
            select(Flight.scheduled_departure, Flight.actual_departure)
            .where(Flight.id.in_(flight_ids), Flight.actual_departure.is_not(None))).all()
        flights = {
            "total_flights": sum(by_status.values()),
            "scheduled_flights": g(FlightStatus.SCHEDULED), "check_in_open_flights": g(FlightStatus.CHECK_IN_OPEN),
            "boarding_flights": g(FlightStatus.BOARDING), "delayed_flights": g(FlightStatus.DELAYED),
            "cancelled_flights": g(FlightStatus.CANCELLED), "departed_flights": g(FlightStatus.DEPARTED),
            "arrived_flights": g(FlightStatus.ARRIVED),
            "on_time_performance_pct": on_time_performance([tuple(r) for r in departed_rows]),
        }

        # ---- resources (current state) ----
        def scoped(stmt, model):
            if airport_id:
                stmt = stmt.join(Terminal, Terminal.id == model.terminal_id).where(Terminal.airport_id == airport_id)
            return stmt
        counters = scoped(select(CheckInCounter.status, func.count()).where(CheckInCounter.is_active.is_(True)),
                          CheckInCounter).group_by(CheckInCounter.status)
        counter_counts = dict(self.db.execute(counters).all())
        gates = scoped(select(Gate.status, func.count()).where(Gate.is_active.is_(True)), Gate).group_by(Gate.status)
        gate_counts = dict(self.db.execute(gates).all())
        eq_counts = self.repo.count_by(Equipment.status)
        staff_counts = self.repo.count_by(GroundStaff.availability_status,
                                          select(GroundStaff).where(GroundStaff.is_active.is_(True)))
        resources = {
            "active_checkin_counters": counter_counts.get(CounterStatus.OPEN, 0),
            "total_checkin_counters": sum(counter_counts.values()),
            "available_gates": gate_counts.get(GateStatus.AVAILABLE, 0),
            "total_gates": sum(gate_counts.values()),
            "equipment_available": eq_counts.get(EquipmentStatus.AVAILABLE, 0),
            "equipment_in_use": eq_counts.get(EquipmentStatus.IN_USE, 0),
            "equipment_in_maintenance": eq_counts.get(EquipmentStatus.MAINTENANCE, 0),
            "staff_available": staff_counts.get(StaffAvailability.AVAILABLE, 0),
            "staff_on_task": staff_counts.get(StaffAvailability.ON_TASK, 0),
        }

        # ---- baggage (for flights in range) ----
        bstmt = select(Baggage).where(Baggage.flight_id.in_(flight_ids))
        bag_counts = self.repo.count_by(Baggage.status, bstmt)
        on_hold = self.db.scalar(select(func.count(Baggage.id)).where(
            Baggage.flight_id.in_(flight_ids), Baggage.is_on_hold.is_(True))) or 0
        baggage = {
            "baggage_processed": sum(bag_counts.values()),
            "baggage_delivered": bag_counts.get(BaggageStatus.DELIVERED, 0),
            "delayed_baggage": bag_counts.get(BaggageStatus.DELAYED, 0),
            "missing_baggage": bag_counts.get(BaggageStatus.MISSING, 0),
            "baggage_on_hold": on_hold,
        }

        # ---- operations ----
        task_counts = self.repo.count_by(GroundTask.status, select(GroundTask).where(GroundTask.flight_id.in_(flight_ids)))
        ta_stmt = select(Turnaround).where(Turnaround.flight_id.in_(flight_ids))
        ta_counts = self.repo.count_by(Turnaround.status, ta_stmt)
        avg_ta = self.db.scalar(select(func.avg(Turnaround.total_duration_minutes)).where(
            Turnaround.flight_id.in_(flight_ids), Turnaround.status == TurnaroundStatus.COMPLETED))
        delayed_ta = self.db.scalar(select(func.count(Turnaround.id)).where(
            Turnaround.flight_id.in_(flight_ids), Turnaround.delay_minutes > 0)) or 0
        inc = select(Incident)
        if start:
            inc = inc.where(Incident.reported_at >= start)
        if end:
            inc = inc.where(Incident.reported_at < end)
        inc_status = self.repo.count_by(Incident.status, inc)
        inc_sev_stmt = inc.where(Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.INVESTIGATING,
                                                      IncidentStatus.IN_PROGRESS]))
        inc_sev = self.repo.count_by(Incident.severity, inc_sev_stmt)
        total_delay = self.db.scalar(select(func.coalesce(func.sum(FlightDelay.delay_minutes), 0)).where(
            FlightDelay.flight_id.in_(flight_ids))) or 0
        operations = {
            "ground_tasks_pending": task_counts.get(TaskStatus.PENDING, 0) + task_counts.get(TaskStatus.ASSIGNED, 0),
            "ground_tasks_in_progress": task_counts.get(TaskStatus.IN_PROGRESS, 0),
            "ground_tasks_completed": task_counts.get(TaskStatus.COMPLETED, 0),
            "turnarounds_in_progress": ta_counts.get(TurnaroundStatus.IN_PROGRESS, 0),
            "turnarounds_completed": ta_counts.get(TurnaroundStatus.COMPLETED, 0),
            "avg_turnaround_duration_minutes": round(float(avg_ta), 1) if avg_ta is not None else None,
            "delayed_turnarounds": delayed_ta,
            "open_incidents": sum(v for k, v in inc_status.items()
                                  if k in (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING, IncidentStatus.IN_PROGRESS)),
            "critical_incidents": inc_sev.get(Severity.CRITICAL, 0),
            "total_incidents": sum(inc_status.values()),
            "total_delay_minutes": int(total_delay),
        }
        return {"date_from": date_from, "date_to": date_to, "airport_id": airport_id, "flights": flights,
                "resources": resources, "baggage": baggage, "operations": operations}
