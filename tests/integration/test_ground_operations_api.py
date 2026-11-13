from datetime import timedelta

from app.utils.datetime_utils import utcnow
from tests.conftest import API, PASSWORD, login


def test_staff_registration_and_filters(client, admin, factory):
    sup = factory.staff(designation="Supervisor")
    s = factory.staff(supervisor_id=sup["id"], skills=["Loading", "pushback"])
    assert s["skills"] == ["loading", "pushback"]
    assert client.get(f"{API}/ground-staff", headers=admin, params={"skill": "pushback"}).json()["total"] == 1
    assert [m["id"] for m in client.get(f"{API}/ground-staff/{sup['id']}/team", headers=admin).json()] == [s["id"]]
    # no reporting cycles
    r = client.patch(f"{API}/ground-staff/{sup['id']}", headers=admin, json={"supervisor_id": s["id"]})
    assert r.status_code == 400


def test_attendance(client, admin, factory):
    s = factory.staff()
    r = client.post(f"{API}/attendance/{s['id']}/check-in", headers=admin)
    assert r.status_code == 201 and r.json()["status"] in ("PRESENT", "LATE")
    assert client.post(f"{API}/attendance/{s['id']}/check-in", headers=admin).status_code == 409
    assert client.post(f"{API}/attendance/{s['id']}/check-out", headers=admin).json()["check_out_time"]


def test_task_assignment_lifecycle_and_staff_validation(client, admin, factory):
    f = factory.flight()
    s1, s2 = factory.staff(), factory.staff()
    t = factory.post("/ground-tasks", {"flight_id": f["id"], "task_type": "BAGGAGE_LOADING", "priority": "HIGH",
                                       "assigned_staff_id": s1["id"]})
    assert t["status"] == "ASSIGNED"
    assert client.post(f"{API}/ground-tasks/{t['id']}/start", headers=admin, json={}).json()["status"] == "IN_PROGRESS"
    assert client.get(f"{API}/ground-staff/{s1['id']}", headers=admin).json()["availability_status"] == "ON_TASK"
    # staff can't start a second task concurrently
    t2 = factory.post("/ground-tasks", {"flight_id": f["id"], "task_type": "AIRCRAFT_CLEANING",
                                        "assigned_staff_id": s1["id"]})
    r = client.post(f"{API}/ground-tasks/{t2['id']}/start", headers=admin, json={})
    assert r.json()["error"]["code"] == "STAFF_BUSY"
    done = client.post(f"{API}/ground-tasks/{t['id']}/complete", headers=admin, json={"remarks": "done"}).json()
    assert done["status"] == "COMPLETED" and done["completion_time"]
    assert client.get(f"{API}/ground-staff/{s1['id']}", headers=admin).json()["availability_status"] == "AVAILABLE"
    # staff on leave can't be assigned
    client.patch(f"{API}/ground-staff/{s2['id']}/availability", headers=admin, json={"availability_status": "ON_LEAVE"})
    r = client.post(f"{API}/ground-tasks/{t2['id']}/assign", headers=admin, json={"staff_id": s2["id"]})
    assert r.json()["error"]["code"] == "STAFF_UNAVAILABLE"
    logs = client.get(f"{API}/audit-logs", headers=admin, params={"action": "GROUND_TASK_ASSIGNED"}).json()
    assert logs["total"] == 2


def test_my_tasks_and_assignment_notification(client, admin, factory):
    factory.post("/users", {"email": "loader@airportops.com", "full_name": "Loader", "password": PASSWORD,
                            "role": "BAGGAGE_HANDLING_STAFF"})
    worker = login(client, "loader@airportops.com", PASSWORD)
    uid = client.get(f"{API}/auth/me", headers=worker).json()["id"]
    s = factory.staff(user_id=uid)
    f = factory.flight()
    factory.post("/ground-tasks", {"flight_id": f["id"], "task_type": "BAGGAGE_UNLOADING", "assigned_staff_id": s["id"]})
    assert client.get(f"{API}/ground-tasks/my", headers=worker).json()["total"] == 1
    notes = client.get(f"{API}/notifications", headers=worker).json()
    assert notes["items"][0]["notification_type"] == "GROUND_TASK_ASSIGNMENT"


def test_turnaround_workflow(client, admin, factory):
    f = factory.flight()
    ta = factory.post("/turnarounds", {"flight_id": f["id"], "target_duration_minutes": 60})
    acts = {a["activity_type"]: a["id"] for a in ta["activities"]}
    assert len(acts) == 9 and ta["status"] == "PLANNED"
    base = f"{API}/turnarounds/{ta['id']}/activities"
    # prerequisites enforced
    r = client.post(f"{base}/{acts['AIRCRAFT_CLEANING']}/start", headers=admin, json={})
    assert r.json()["error"]["code"] == "PREREQUISITES_PENDING"

    t0 = utcnow() - timedelta(hours=3)
    clock = {"t": t0}

    def run(activity, minutes, **extra):
        start = clock["t"]
        end = start + timedelta(minutes=minutes)
        r1 = client.post(f"{base}/{acts[activity]}/start", headers=admin,
                         json={"start_time": start.isoformat(), "assigned_team": "Ramp A"})
        assert r1.status_code == 200, r1.text
        r2 = client.post(f"{base}/{acts[activity]}/complete", headers=admin,
                         json={"completion_time": end.isoformat(), **extra})
        clock["t"] = end
        return r2

    assert run("AIRCRAFT_ARRIVAL", 5).status_code == 200
    # parking stand must be set before PARKING_ASSIGNMENT completes
    client.post(f"{base}/{acts['PARKING_ASSIGNMENT']}/start", headers=admin, json={"start_time": clock["t"].isoformat()})
    r = client.post(f"{base}/{acts['PARKING_ASSIGNMENT']}/complete", headers=admin,
                    json={"completion_time": (clock["t"] + timedelta(minutes=4)).isoformat()})
    assert r.status_code == 400
    client.patch(f"{API}/turnarounds/{ta['id']}/parking", headers=admin, json={"parking_stand": "s12"})
    client.post(f"{base}/{acts['PARKING_ASSIGNMENT']}/complete", headers=admin,
                json={"completion_time": (clock["t"] + timedelta(minutes=4)).isoformat()})
    clock["t"] += timedelta(minutes=4)
    assert run("PASSENGER_DISEMBARKATION", 10).status_code == 200
    assert run("BAGGAGE_UNLOADING", 12).status_code == 200
    # overrun without reason is rejected, with reason accepted
    r = run("AIRCRAFT_CLEANING", 25)
    assert r.json()["error"]["code"] == "DELAY_REASON_REQUIRED"
    r = client.post(f"{base}/{acts['AIRCRAFT_CLEANING']}/complete", headers=admin,
                    json={"completion_time": clock["t"].isoformat(), "delay_reason": "Extra cabin waste"})
    assert r.json()["is_delayed"] and r.json()["delay_minutes"] == 10
    for a, m in (("REFUELING_COORDINATION", 15), ("BAGGAGE_LOADING", 15), ("FINAL_INSPECTION", 8),
                 ("DEPARTURE_READINESS", 3)):
        assert run(a, m).status_code == 200
    final = client.get(f"{API}/turnarounds/{ta['id']}", headers=admin).json()
    assert final["status"] == "COMPLETED" and final["parking_stand"] == "S12"
    assert final["total_duration_minutes"] == 97 and final["delay_minutes"] == 37 and final["is_delayed"]
    assert "AIRCRAFT_CLEANING" in final["delay_reason"]
    rep = client.get(f"{API}/reports/turnarounds", headers=admin).json()
    assert rep["items"][0]["delayed_activities"] == 1
