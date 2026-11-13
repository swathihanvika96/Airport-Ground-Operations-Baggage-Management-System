"""Operational reports. Each returns (rows, summary); routes add sorting, pagination and CSV export."""
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.attendance import StaffAttendance
from app.models.baggage import Baggage
from app.models.baggage_screening import BaggageScreening
from app.models.baggage_tracking import BaggageTrackingEvent
from app.models.checkin import CheckIn
from app.models.equipment import Equipment
from app.models.equipment_assignment import EquipmentAssignment
from app.models.equipment_maintenance import EquipmentMaintenance
from app.models.flight import Flight
from app.models.flight_delay import FlightDelay
from app.models.ground_staff import GroundStaff
from app.models.ground_task import GroundTask
from app.models.passenger import PassengerFlight
from app.models.turnaround import Turnaround
from app.repositories.report_repository import ReportRepository
from app.services.dashboard_service import on_time_performance
from app.services.delay_service import total_delay_minutes
from app.utils.datetime_utils import minutes_between, utcnow
from app.utils.enums import (
    AssignmentStatus,
    AttendanceStatus,
    BaggageStatus,
    BookingStatus,
    CheckInStatus,
    FlightStatus,
    TaskStatus,
)

Rows = list[dict]


def _avg(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReportRepository(db)

    def _flights(self, start, end, airport_id=None) -> list[Flight]:
        stmt = select(Flight).options(selectinload(Flight.departure_airport), selectinload(Flight.arrival_airport),
                                      selectinload(Flight.gate))
        if start:
            stmt = stmt.where(Flight.scheduled_departure >= start)
        if end:
            stmt = stmt.where(Flight.scheduled_departure < end)
        if airport_id:
            stmt = stmt.where((Flight.departure_airport_id == airport_id) | (Flight.arrival_airport_id == airport_id))
        return self.repo.scalars(stmt.order_by(Flight.scheduled_departure))

    def _count_map(self, stmt) -> dict:
        return {k: v for k, v in self.repo.rows(stmt)}

    # 1. Daily flight operations
    def daily_flight_operations(self, start: datetime, end: datetime, airport_id=None) -> tuple[Rows, dict]:
        from sqlalchemy import func
        flights = self._flights(start, end, airport_id)
        ids = [f.id for f in flights] or [-1]
        booked = self._count_map(select(PassengerFlight.flight_id, func.count()).where(
            PassengerFlight.flight_id.in_(ids), PassengerFlight.status != BookingStatus.CANCELLED)
            .group_by(PassengerFlight.flight_id))
        checked = self._count_map(select(CheckIn.flight_id, func.count()).where(
            CheckIn.flight_id.in_(ids), CheckIn.status != CheckInStatus.CANCELLED).group_by(CheckIn.flight_id))
        bags = self._count_map(select(Baggage.flight_id, func.count()).where(Baggage.flight_id.in_(ids))
                               .group_by(Baggage.flight_id))
        rows = []
        for f in flights:
            rows.append({
                "flight_id": f.id, "flight_number": f.flight_number, "airline": f.airline_name,
                "route": f"{f.departure_airport_code}-{f.arrival_airport_code}", "aircraft": f.aircraft_type,
                "scheduled_departure": f.scheduled_departure, "estimated_departure": f.estimated_departure,
                "actual_departure": f.actual_departure, "actual_arrival": f.actual_arrival,
                "status": f.status.value, "gate": f.gate_number,
                "delay_minutes": total_delay_minutes(f.scheduled_departure, f.actual_departure or f.current_departure),
                "passengers_booked": booked.get(f.id, 0), "passengers_checked_in": checked.get(f.id, 0),
                "baggage_count": bags.get(f.id, 0),
            })
        by_status = defaultdict(int)
        for r in rows:
            by_status[r["status"]] += 1
        summary = {"total_flights": len(rows), "by_status": dict(by_status),
                   "total_passengers_checked_in": sum(r["passengers_checked_in"] for r in rows),
                   "total_delay_minutes": sum(r["delay_minutes"] for r in rows)}
        return rows, summary

    # 2. Monthly flight performance (grouped by airline)
    def monthly_flight_performance(self, start, end, airport_id=None) -> tuple[Rows, dict]:
        flights = self._flights(start, end, airport_id)
        groups: dict[str, list[Flight]] = defaultdict(list)
        for f in flights:
            groups[f.airline_code].append(f)
        rows = []
        for code, fl in groups.items():
            delays = [total_delay_minutes(f.scheduled_departure, f.actual_departure or f.current_departure)
                      for f in fl if f.status != FlightStatus.CANCELLED]
            departed = [(f.scheduled_departure, f.actual_departure) for f in fl if f.actual_departure]
            rows.append({
                "airline_code": code, "airline": fl[0].airline_name, "total_flights": len(fl),
                "completed_flights": sum(1 for f in fl if f.status in (FlightStatus.DEPARTED, FlightStatus.ARRIVED)),
                "cancelled_flights": sum(1 for f in fl if f.status == FlightStatus.CANCELLED),
                "delayed_flights": sum(1 for d in delays if d > 15),
                "avg_delay_minutes": _avg(delays) or 0, "max_delay_minutes": max(delays, default=0),
                "on_time_performance_pct": on_time_performance(departed),
                "cancellation_rate_pct": round(100 * sum(1 for f in fl if f.status == FlightStatus.CANCELLED) / len(fl), 2),
            })
        all_departed = [(f.scheduled_departure, f.actual_departure) for f in flights if f.actual_departure]
        summary = {"total_flights": len(flights), "airlines": len(rows),
                   "overall_on_time_performance_pct": on_time_performance(all_departed)}
        return rows, summary

    # 3. Baggage handling (per flight)
    def baggage_handling(self, start, end, airport_id=None) -> tuple[Rows, dict]:
        flights = {f.id: f for f in self._flights(start, end, airport_id)}
        bags = self.repo.scalars(select(Baggage).where(Baggage.flight_id.in_(list(flights) or [-1])))
        screened_ids = set(self.repo.scalars(select(BaggageScreening.baggage_id).where(
            BaggageScreening.baggage_id.in_([b.id for b in bags] or [-1]))))
        per = defaultdict(list)
        for b in bags:
            per[b.flight_id].append(b)
        rows = []
        for fid, bl in per.items():
            f = flights[fid]
            st = defaultdict(int)
            for b in bl:
                st[b.status] += 1
            rows.append({
                "flight_id": fid, "flight_number": f.flight_number, "scheduled_departure": f.scheduled_departure,
                "total_bags": len(bl), "total_weight_kg": round(sum(b.weight_kg for b in bl), 1),
                "screened": sum(1 for b in bl if b.id in screened_ids), "on_hold": sum(1 for b in bl if b.is_on_hold),
                "loaded_or_beyond": sum(st[s] for s in (BaggageStatus.LOADED, BaggageStatus.IN_TRANSIT,
                                                        BaggageStatus.UNLOADED, BaggageStatus.DELIVERED)),
                "delivered": st[BaggageStatus.DELIVERED], "delayed": st[BaggageStatus.DELAYED],
                "missing": st[BaggageStatus.MISSING],
                "mishandling_rate_pct": round(100 * (st[BaggageStatus.DELAYED] + st[BaggageStatus.MISSING]) / len(bl), 2),
            })
        summary = {"total_bags": len(bags), "delivered": sum(r["delivered"] for r in rows),
                   "delayed": sum(r["delayed"] for r in rows), "missing": sum(r["missing"] for r in rows),
                   "total_weight_kg": round(sum(r["total_weight_kg"] for r in rows), 1)}
        return rows, summary

    # 4. Missing baggage
    def missing_baggage(self, start, end, airport_id=None) -> tuple[Rows, dict]:
        stmt = select(Baggage).where(Baggage.status == BaggageStatus.MISSING)
        bags = self.repo.scalars(stmt)
        now = utcnow()
        rows = []
        for b in bags:
            event = self.db.scalar(select(BaggageTrackingEvent).where(
                BaggageTrackingEvent.baggage_id == b.id, BaggageTrackingEvent.status == BaggageStatus.MISSING)
                .order_by(BaggageTrackingEvent.timestamp.desc()).limit(1))
            reported = event.timestamp if event else b.updated_at
            if (start and reported < start) or (end and reported >= end):
                continue
            if airport_id and airport_id not in (b.flight.departure_airport_id, b.flight.arrival_airport_id):
                continue
            rows.append({
                "baggage_id": b.id, "tag_number": b.tag_number, "passenger_id": b.passenger_id,
                "passenger_name": b.passenger.full_name, "flight_number": b.flight.flight_number,
                "destination": b.destination, "category": b.category.value, "weight_kg": b.weight_kg,
                "last_known_location": b.current_location, "reported_missing_at": reported,
                "hours_missing": round((now - reported).total_seconds() / 3600, 1),
                "remarks": event.remarks if event else None,
            })
        return rows, {"total_missing": len(rows)}

    # 5. Ground staff performance
    def staff_performance(self, start, end, airport_id=None) -> tuple[Rows, dict]:
        staff = self.repo.scalars(select(GroundStaff))
        tstmt = select(GroundTask).where(GroundTask.assigned_staff_id.is_not(None))
        if start:
            tstmt = tstmt.where(GroundTask.created_at >= start)
        if end:
            tstmt = tstmt.where(GroundTask.created_at < end)
        tasks = defaultdict(list)
        for t in self.repo.scalars(tstmt):
            tasks[t.assigned_staff_id].append(t)
        astmt = select(StaffAttendance)
        if start:
            astmt = astmt.where(StaffAttendance.attendance_date >= start.date())
        if end:
            astmt = astmt.where(StaffAttendance.attendance_date < end.date())
        att = defaultdict(lambda: defaultdict(int))
        for a in self.repo.scalars(astmt):
            att[a.staff_id][a.status] += 1
        rows = []
        for s in staff:
            tl = tasks.get(s.id, [])
            done = [t for t in tl if t.status == TaskStatus.COMPLETED]
            durations = [minutes_between(t.start_time, t.completion_time) for t in done]
            with_due = [t for t in done if t.due_time]
            on_time = sum(1 for t in with_due if t.completion_time <= t.due_time)
            rows.append({
                "staff_id": s.id, "employee_code": s.employee_code, "full_name": s.full_name,
                "department": s.department.value, "designation": s.designation,
                "tasks_assigned": len(tl), "tasks_completed": len(done),
                "tasks_in_progress": sum(1 for t in tl if t.status == TaskStatus.IN_PROGRESS),
                "tasks_cancelled": sum(1 for t in tl if t.status == TaskStatus.CANCELLED),
                "completion_rate_pct": round(100 * len(done) / len(tl), 2) if tl else None,
                "avg_completion_minutes": _avg(durations),
                "on_time_completion_pct": round(100 * on_time / len(with_due), 2) if with_due else None,
                "days_present": att[s.id][AttendanceStatus.PRESENT], "days_late": att[s.id][AttendanceStatus.LATE],
                "days_absent": att[s.id][AttendanceStatus.ABSENT],
            })
        summary = {"staff_count": len(rows), "total_tasks": sum(r["tasks_assigned"] for r in rows),
                   "total_completed": sum(r["tasks_completed"] for r in rows)}
        return rows, summary

    # 6. Equipment utilisation
    def equipment_utilization(self, start, end, airport_id=None) -> tuple[Rows, dict]:
        stmt = select(Equipment)
        if airport_id:
            stmt = stmt.where(Equipment.airport_id == airport_id)
        equipment = self.repo.scalars(stmt)
        astmt = select(EquipmentAssignment).where(EquipmentAssignment.status != AssignmentStatus.CANCELLED)
        if start:
            astmt = astmt.where(EquipmentAssignment.start_time >= start)
        if end:
            astmt = astmt.where(EquipmentAssignment.start_time < end)
        assigns = defaultdict(list)
        for a in self.repo.scalars(astmt):
            assigns[a.equipment_id].append(a)
        maint = defaultdict(int)
        for m in self.repo.scalars(select(EquipmentMaintenance)):
            maint[m.equipment_id] += 1
        period_hours = (end - start).total_seconds() / 3600 if start and end else None
        rows = []
        for e in equipment:
            al = assigns.get(e.id, [])
            hours = sum(a.usage_hours if a.usage_hours is not None else
                        (a.end_time - a.start_time).total_seconds() / 3600 for a in al)
            rows.append({
                "equipment_id": e.id, "equipment_code": e.equipment_code, "name": e.name,
                "equipment_type": e.equipment_type.value, "status": e.status.value,
                "assignments": len(al), "flights_served": len({a.flight_id for a in al}),
                "hours_used": round(hours, 2), "lifetime_usage_hours": e.usage_hours,
                "utilization_pct": round(100 * hours / period_hours, 2) if period_hours else None,
                "maintenance_records": maint[e.id], "next_maintenance_date": e.next_maintenance_date,
            })
        summary = {"equipment_count": len(rows), "total_assignments": sum(r["assignments"] for r in rows),
                   "total_hours_used": round(sum(r["hours_used"] for r in rows), 2)}
        return rows, summary

    # 7. Flight delay analysis
    def delay_analysis(self, start, end, airport_id=None) -> tuple[Rows, dict]:
        stmt = select(FlightDelay)
        if start:
            stmt = stmt.where(FlightDelay.recorded_at >= start)
        if end:
            stmt = stmt.where(FlightDelay.recorded_at < end)
        delays = self.repo.scalars(stmt)
        if airport_id:
            delays = [d for d in delays if airport_id in (d.flight.departure_airport_id, d.flight.arrival_airport_id)]
        groups = defaultdict(list)
        for d in delays:
            groups[d.delay_category.value].append(d)
        total_minutes = sum(d.delay_minutes for d in delays) or 0
        rows = [{
            "delay_category": cat, "delay_events": len(dl), "flights_affected": len({d.flight_id for d in dl}),
            "total_delay_minutes": sum(d.delay_minutes for d in dl),
            "avg_delay_minutes": _avg([d.delay_minutes for d in dl]),
            "max_delay_minutes": max(d.delay_minutes for d in dl),
            "share_of_total_pct": round(100 * sum(d.delay_minutes for d in dl) / total_minutes, 2) if total_minutes else 0,
        } for cat, dl in groups.items()]
        by_dept = defaultdict(int)
        for d in delays:
            by_dept[d.responsible_department.value if d.responsible_department else "UNASSIGNED"] += d.delay_minutes
        summary = {"delay_events": len(delays), "total_delay_minutes": total_minutes,
                   "flights_affected": len({d.flight_id for d in delays}),
                   "minutes_by_department": dict(by_dept)}
        return rows, summary

    # 8. Aircraft turnaround
    def turnaround_report(self, start, end, airport_id=None) -> tuple[Rows, dict]:
        stmt = select(Turnaround).options(selectinload(Turnaround.activities))
        if start:
            stmt = stmt.where(Turnaround.created_at >= start)
        if end:
            stmt = stmt.where(Turnaround.created_at < end)
        tas = self.repo.scalars(stmt)
        if airport_id:
            tas = [t for t in tas if t.flight.departure_airport_id == airport_id]
        rows = []
        for t in tas:
            delayed = [a for a in t.activities if a.is_delayed]
            rows.append({
                "turnaround_id": t.id, "flight_number": t.flight.flight_number, "parking_stand": t.parking_stand,
                "status": t.status.value, "actual_start": t.actual_start, "actual_end": t.actual_end,
                "target_minutes": t.target_duration_minutes, "duration_minutes": t.total_duration_minutes,
                "over_target_minutes": t.delay_minutes,
                "activities_completed": sum(1 for a in t.activities if a.status.value == "COMPLETED"),
                "activities_total": len(t.activities), "delayed_activities": len(delayed),
                "delay_reasons": "; ".join(f"{a.activity_type.value}: {a.delay_reason}" for a in delayed) or None,
            })
        done = [r["duration_minutes"] for r in rows if r["duration_minutes"] is not None]
        summary = {"turnarounds": len(rows), "completed": len(done), "avg_duration_minutes": _avg(done),
                   "over_target": sum(1 for r in rows if r["over_target_minutes"] > 0)}
        return rows, summary
