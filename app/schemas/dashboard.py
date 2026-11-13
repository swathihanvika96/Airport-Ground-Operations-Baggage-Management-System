from datetime import date

from pydantic import BaseModel


class FlightMetrics(BaseModel):
    total_flights: int
    scheduled_flights: int
    check_in_open_flights: int
    boarding_flights: int
    delayed_flights: int
    cancelled_flights: int
    departed_flights: int
    arrived_flights: int
    on_time_performance_pct: float | None


class ResourceMetrics(BaseModel):
    active_checkin_counters: int
    total_checkin_counters: int
    available_gates: int
    total_gates: int
    equipment_available: int
    equipment_in_use: int
    equipment_in_maintenance: int
    staff_available: int
    staff_on_task: int


class BaggageMetrics(BaseModel):
    baggage_processed: int
    baggage_delivered: int
    delayed_baggage: int
    missing_baggage: int
    baggage_on_hold: int


class OperationsMetrics(BaseModel):
    ground_tasks_pending: int
    ground_tasks_in_progress: int
    ground_tasks_completed: int
    turnarounds_in_progress: int
    turnarounds_completed: int
    avg_turnaround_duration_minutes: float | None
    delayed_turnarounds: int
    open_incidents: int
    critical_incidents: int
    total_incidents: int
    total_delay_minutes: int


class DashboardOverview(BaseModel):
    date_from: date | None
    date_to: date | None
    airport_id: int | None
    flights: FlightMetrics
    resources: ResourceMetrics
    baggage: BaggageMetrics
    operations: OperationsMetrics
