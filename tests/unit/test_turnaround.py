from datetime import datetime, timedelta

from app.core.constants import TURNAROUND_ACTIVITY_PLAN, TURNAROUND_PREREQUISITES
from app.services.attendance_service import attendance_status_for
from app.services.turnaround_service import compute_activity_delay
from app.utils.enums import AttendanceStatus, Shift, TurnaroundActivityType as TA


def test_plan_has_all_nine_activities_in_order():
    types = [a for a, _, _ in TURNAROUND_ACTIVITY_PLAN]
    assert types[0] == TA.AIRCRAFT_ARRIVAL and types[-1] == TA.DEPARTURE_READINESS
    assert len(types) == 9 and set(types) == set(TA)


def test_prerequisites_reference_earlier_activities():
    order = {a: i for i, (a, _, _) in enumerate(TURNAROUND_ACTIVITY_PLAN)}
    for activity, prereqs in TURNAROUND_PREREQUISITES.items():
        assert all(order[p] < order[activity] for p in prereqs)


def test_activity_delay_calculation():
    s = datetime(2030, 1, 1, 10, 0)
    assert compute_activity_delay(15, s, s + timedelta(minutes=12)) == (12, 0)
    assert compute_activity_delay(15, s, s + timedelta(minutes=27)) == (27, 12)


def test_attendance_late_detection():
    assert attendance_status_for(Shift.MORNING, datetime(2030, 1, 1, 6, 10)) == AttendanceStatus.PRESENT
    assert attendance_status_for(Shift.MORNING, datetime(2030, 1, 1, 6, 30)) == AttendanceStatus.LATE
