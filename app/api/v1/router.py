"""Aggregates every v1 router."""
from fastapi import APIRouter

from app.api.v1.airports.routes import router as airports
from app.api.v1.audit.routes import router as audit
from app.api.v1.auth.routes import router as auth, users_router
from app.api.v1.baggage.routes import router as baggage
from app.api.v1.baggage.screening_routes import router as screening
from app.api.v1.baggage.tracking_routes import router as tracking
from app.api.v1.checkin.routes import router as checkin
from app.api.v1.counters.routes import router as counters
from app.api.v1.dashboard.routes import router as dashboard
from app.api.v1.delays.routes import router as delays
from app.api.v1.equipment.assignment_routes import router as equipment_assignments
from app.api.v1.equipment.maintenance_routes import router as equipment_maintenance
from app.api.v1.equipment.routes import router as equipment
from app.api.v1.flights.routes import router as flights
from app.api.v1.gates.routes import router as gates
from app.api.v1.ground_operations.attendance_routes import router as attendance
from app.api.v1.ground_operations.staff_routes import router as staff
from app.api.v1.ground_operations.task_routes import router as tasks
from app.api.v1.ground_operations.turnaround_routes import router as turnarounds
from app.api.v1.incidents.routes import router as incidents
from app.api.v1.notifications.routes import router as notifications
from app.api.v1.passengers.routes import router as passengers
from app.api.v1.reports._common import export_router as report_export
from app.api.v1.reports.baggage_reports import router as baggage_reports
from app.api.v1.reports.delay_reports import router as delay_reports
from app.api.v1.reports.equipment_reports import router as equipment_reports
from app.api.v1.reports.flight_reports import router as flight_reports
from app.api.v1.reports.staff_reports import router as staff_reports
from app.api.v1.reports.turnaround_reports import router as turnaround_reports
from app.api.v1.resources.routes import router as resources
from app.api.v1.terminals.routes import router as terminals

api_router = APIRouter()
for r in (
    # Day 1
    auth, users_router, airports, terminals, flights, gates, counters,
    # Day 2 (tracking/screening before baggage so static paths win over /baggage/{id})
    passengers, checkin, tracking, screening, baggage,
    # Day 3
    staff, attendance, tasks, turnarounds, equipment, equipment_assignments, equipment_maintenance, incidents,
    # Day 4
    delays, resources, notifications, dashboard, flight_reports, baggage_reports, staff_reports,
    equipment_reports, delay_reports, turnaround_reports, report_export,
    # Day 5
    audit,
):
    api_router.include_router(r)
