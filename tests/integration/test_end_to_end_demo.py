"""Mandatory end-to-end demo:
Admin Login -> Register Airport -> Create Terminal -> Register Flight -> Assign Gate -> Register Passenger ->
Complete Check-in -> Generate Boarding Pass Reference -> Register Baggage -> Complete Screening -> Track Baggage ->
Assign Ground Staff -> Execute Turnaround Tasks -> Allocate Equipment -> Record Flight Delay -> Update Flight Status ->
View Dashboard -> Generate Reports -> Verify Audit Logs
"""
from datetime import timedelta

from app.core.config import settings
from app.utils.datetime_utils import utcnow
from tests.conftest import API


def test_end_to_end_demo(client):
    def call(method, path, code=200, **kw):
        r = getattr(client, method)(f"{API}{path}", headers=H, **kw)
        assert r.status_code == code, f"{method.upper()} {path}: {r.text}"
        return r.json() if r.headers.get("content-type", "").startswith("application/json") else r

    # 1. Admin login (OAuth2 password flow)
    tok = client.post(f"{API}/auth/token", data={"username": settings.FIRST_SUPERUSER_EMAIL,
                                                  "password": settings.FIRST_SUPERUSER_PASSWORD}).json()
    H = {"Authorization": f"Bearer {tok['access_token']}"}
    # 2. Register airports
    blr = call("post", "/airports", 201, json={"code": "BLR", "icao_code": "VOBL", "name": "Kempegowda Intl",
                                               "city": "Bengaluru", "country": "India"})
    goi = call("post", "/airports", 201, json={"code": "GOI", "name": "Goa Intl", "city": "Dabolim", "country": "India"})
    # 3. Terminal + gate + counter
    t1 = call("post", "/terminals", 201, json={"airport_id": blr["id"], "code": "T1", "name": "Terminal 1",
                                               "capacity": 4000})
    gate = call("post", "/gates", 201, json={"terminal_id": t1["id"], "gate_number": "A5"})
    counter = call("post", "/counters", 201, json={"terminal_id": t1["id"], "counter_number": "C01"})
    # 4. Register flight
    dep = utcnow() + timedelta(hours=3)
    flight = call("post", "/flights", 201, json={
        "flight_number": "AI501", "airline_name": "Air India", "airline_code": "AI", "aircraft_type": "A320neo",
        "departure_airport_id": blr["id"], "arrival_airport_id": goi["id"], "departure_terminal_id": t1["id"],
        "scheduled_departure": dep.isoformat(), "scheduled_arrival": (dep + timedelta(minutes=80)).isoformat()})
    fid = flight["id"]
    # 5. Assign gate (+ counter) and open check-in
    call("post", f"/gates/{gate['id']}/assign", 201, json={"flight_id": fid})
    call("post", f"/counters/{counter['id']}/assign", 201, json={"flight_id": fid})
    call("patch", f"/flights/{fid}/status", json={"status": "CHECK_IN_OPEN"})
    # 6. Register passenger (synthetic) mapped to the flight
    pax = call("post", "/passengers", 201, json={"first_name": "Asha", "last_name": "Synthetic",
                                                 "id_reference": "SYN000001", "flight_id": fid})
    # 7-8. Check-in -> boarding pass reference
    ci = call("post", "/checkin", 201, json={"passenger_id": pax["id"], "flight_id": fid, "seat_number": "14C"})
    bp_ref = ci["boarding_pass"]["reference"]
    assert bp_ref.startswith("BP-AI501-") and ci["boarding_pass"]["gate_number"] == "A5"
    assert ci["checkin"]["counter_id"] == counter["id"]
    # 9. Register baggage
    bag = call("post", "/baggage", 201, json={"passenger_id": pax["id"], "flight_id": fid, "weight_kg": 18.5})
    # 10. Complete screening
    call("patch", f"/baggage/{bag['id']}/status", json={"status": "CHECKIN_COMPLETED"})
    call("post", f"/baggage/{bag['id']}/screenings", 201, json={"result": "CLEARED", "machine_id": "XR-2"})
    # 11. Track baggage
    for s in ("SORTING", "LOADED"):
        call("patch", f"/baggage/{bag['id']}/status", json={"status": s, "location": f"{s} area"})
    track = call("get", f"/baggage/track/{bag['tag_number']}")
    assert track["baggage"]["status"] == "LOADED" and len(track["timeline"]) == 5
    # 12. Assign ground staff (resource allocation + task)
    staff = call("post", "/ground-staff", 201, json={"employee_code": "GS100", "full_name": "Ravi Kumar",
                                                     "department": "RAMP_OPERATIONS", "designation": "Ramp Agent",
                                                     "skills": ["loading"]})
    call("post", "/resources/allocate", 201, json={"resource_type": "STAFF", "resource_id": staff["id"],
                                                   "flight_id": fid, "role_description": "Ramp lead"})
    task = call("post", "/ground-tasks", 201, json={"flight_id": fid, "task_type": "BAGGAGE_LOADING",
                                                    "priority": "HIGH", "assigned_staff_id": staff["id"]})
    call("post", f"/ground-tasks/{task['id']}/start", json={})
    call("post", f"/ground-tasks/{task['id']}/complete", json={"remarks": "All bags loaded"})
    # 13. Execute turnaround tasks
    ta = call("post", "/turnarounds", 201, json={"flight_id": fid, "parking_stand": "S7"})
    t = utcnow() - timedelta(minutes=70)
    for act in ta["activities"]:
        minutes = act["planned_duration_minutes"]
        base = f"/turnarounds/{ta['id']}/activities/{act['id']}"
        call("post", f"{base}/start", json={"start_time": t.isoformat(), "assigned_team": "Team Alpha"})
        t += timedelta(minutes=minutes)
        call("post", f"{base}/complete", json={"completion_time": t.isoformat()})
    ta = call("get", f"/turnarounds/{ta['id']}")
    assert ta["status"] == "COMPLETED" and ta["total_duration_minutes"] == 105
    # 14. Allocate equipment
    tug = call("post", "/equipment", 201, json={"equipment_code": "TUG-01", "name": "Pushback Tug",
                                                "equipment_type": "AIRCRAFT_TUG"})
    call("post", "/equipment-assignments", 201, json={"equipment_id": tug["id"], "flight_id": fid})
    # 15. Record flight delay
    delay = call("post", "/delays", 201, json={"flight_id": fid, "delay_category": "GROUND_OPERATIONS",
                                                "reason": "Late fuel bowser", "delay_minutes": 25,
                                                "responsible_department": "FUEL_SERVICES"})
    assert delay["delay_minutes"] == 25
    assert call("get", f"/flights/{fid}")["status"] == "DELAYED"
    # 16. Update flight status -> boarding -> departed
    call("patch", f"/flights/{fid}/status", json={"status": "BOARDING"})
    call("post", f"/checkin/{ci['checkin']['id']}/board")
    departed = call("patch", f"/flights/{fid}/status", json={"status": "DEPARTED"})
    assert departed["actual_departure"]
    assert call("get", f"/gates/{gate['id']}")["status"] == "AVAILABLE"       # resources released
    assert call("get", f"/equipment/{tug['id']}")["status"] == "AVAILABLE"
    # 17. Dashboard
    dash = call("get", "/dashboard/overview")
    assert dash["flights"]["departed_flights"] == 1
    assert dash["baggage"]["baggage_processed"] == 1
    assert dash["operations"]["turnarounds_completed"] == 1
    assert dash["operations"]["avg_turnaround_duration_minutes"] == 105
    # 18. Reports (JSON + CSV)
    daily = call("get", "/reports/flights/daily")
    assert daily["items"][0]["flight_number"] == "AI501" and daily["items"][0]["passengers_checked_in"] == 1
    csv_resp = client.get(f"{API}/reports/delays/analysis", headers=H, params={"format": "csv"})
    assert "GROUND_OPERATIONS" in csv_resp.text
    # 19. Audit logs
    actions = {e["action"] for e in call("get", "/audit-logs", params={"size": 200})["items"]}
    for expected in ("USER_LOGIN", "FLIGHT_CREATED", "GATE_ASSIGNED", "CHECKIN_CREATED", "BAGGAGE_STATUS_CHANGED",
                     "GROUND_TASK_ASSIGNED", "EQUIPMENT_ALLOCATED", "FLIGHT_DELAY_RECORDED", "FLIGHT_STATUS_CHANGED"):
        assert expected in actions, expected
    trail = call("get", f"/audit-logs/entity/flight/{fid}")
    assert any(e["action"] == "FLIGHT_DELAY_RECORDED" and e["new_value"]["delay_minutes"] == 25 for e in trail)
