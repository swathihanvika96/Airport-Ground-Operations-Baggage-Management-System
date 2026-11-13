from datetime import timedelta

from app.utils.datetime_utils import utcnow
from tests.conftest import API


def test_create_and_filter_flights(client, admin, factory):
    f = factory.flight(number="AI999")
    assert f["status"] == "SCHEDULED" and f["departure_airport_code"] == "BLR"
    r = client.get(f"{API}/flights", headers=admin, params={"q": "AI999"}).json()
    assert r["total"] == 1
    r = client.get(f"{API}/flights", headers=admin, params={"status": "SCHEDULED", "airline_code": "ai"}).json()
    assert r["total"] == 1


def test_duplicate_flight_rejected(client, admin, factory):
    f = factory.flight(number="AI500")
    dup = {k: f[k] for k in ("flight_number", "airline_name", "airline_code", "aircraft_type",
                             "departure_airport_id", "arrival_airport_id", "scheduled_departure",
                             "scheduled_arrival")}
    assert client.post(f"{API}/flights", headers=admin, json=dup).status_code == 409


def test_status_lifecycle_and_invalid_transition(client, admin, factory):
    f = factory.flight()
    r = client.patch(f"{API}/flights/{f['id']}/status", headers=admin, json={"status": "DEPARTED"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"
    for s in ("CHECK_IN_OPEN", "BOARDING", "DEPARTED", "ARRIVED"):
        r = client.patch(f"{API}/flights/{f['id']}/status", headers=admin, json={"status": s})
        assert r.status_code == 200, r.text
    body = r.json()
    assert body["actual_departure"] and body["actual_arrival"]
    assert client.patch(f"{API}/flights/{f['id']}", headers=admin, json={"aircraft_type": "B737"}).status_code == 400


def test_schedule_change_is_audited(client, admin, factory):
    f = factory.flight()
    new_dep = (utcnow() + timedelta(hours=10)).isoformat()
    new_arr = (utcnow() + timedelta(hours=12)).isoformat()
    client.patch(f"{API}/flights/{f['id']}", headers=admin,
                 json={"scheduled_departure": new_dep, "scheduled_arrival": new_arr})
    logs = client.get(f"{API}/audit-logs", headers=admin,
                      params={"action": "FLIGHT_SCHEDULE_CHANGED", "entity_id": f["id"]}).json()
    assert logs["total"] == 1
    entry = logs["items"][0]
    assert entry["previous_value"]["scheduled_departure"] != entry["new_value"]["scheduled_departure"]


def test_flight_officer_can_create_but_gate_agent_cannot(client, factory):
    officer, gate_agent = factory.user("FLIGHT_OPERATIONS_OFFICER"), factory.user("GATE_AGENT")
    dep, arr, _ = factory.setup_airports()
    start = utcnow() + timedelta(hours=5)
    body = {"flight_number": "AI777", "airline_name": "Air India", "airline_code": "AI", "aircraft_type": "A321",
            "departure_airport_id": dep["id"], "arrival_airport_id": arr["id"],
            "scheduled_departure": start.isoformat(), "scheduled_arrival": (start + timedelta(hours=2)).isoformat()}
    assert client.post(f"{API}/flights", headers=gate_agent, json=body).status_code == 403
    assert client.post(f"{API}/flights", headers=officer, json=body).status_code == 201
