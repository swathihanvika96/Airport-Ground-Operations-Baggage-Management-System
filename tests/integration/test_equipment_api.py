from datetime import date, datetime, timedelta

from tests.conftest import API


def test_equipment_assignment_conflict_and_release(client, admin, factory):
    eq = factory.equipment("AIRCRAFT_TUG")
    f1, f2 = factory.flight(hours_ahead=4), factory.flight(hours_ahead=4)
    a = factory.post("/equipment-assignments", {"equipment_id": eq["id"], "flight_id": f1["id"]})
    assert client.get(f"{API}/equipment/{eq['id']}", headers=admin).json()["status"] == "IN_USE"
    r = client.post(f"{API}/equipment-assignments", headers=admin, json={"equipment_id": eq["id"], "flight_id": f2["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "EQUIPMENT_CONFLICT"
    rel = client.post(f"{API}/equipment-assignments/{a['id']}/release", headers=admin).json()
    assert rel["status"] == "RELEASED" and rel["usage_hours"] is not None
    assert client.get(f"{API}/equipment/{eq['id']}", headers=admin).json()["status"] == "AVAILABLE"
    hist = client.get(f"{API}/equipment/{eq['id']}/usage-history", headers=admin).json()
    assert hist["total"] == 1
    logs = client.get(f"{API}/audit-logs", headers=admin, params={"action": "EQUIPMENT_ALLOCATED"}).json()
    assert logs["total"] == 1


def test_maintenance_blocks_allocation(client, admin, factory):
    eq = factory.equipment("GROUND_POWER_UNIT")
    m = factory.post("/equipment-maintenance", {"equipment_id": eq["id"], "scheduled_date": str(date.today())})
    client.post(f"{API}/equipment-maintenance/{m['id']}/start", headers=admin)
    f = factory.flight()
    r = client.post(f"{API}/equipment-assignments", headers=admin, json={"equipment_id": eq["id"], "flight_id": f["id"]})
    assert r.json()["error"]["code"] == "EQUIPMENT_UNAVAILABLE"
    done = client.post(f"{API}/equipment-maintenance/{m['id']}/complete", headers=admin, json={}).json()
    assert done["status"] == "COMPLETED"
    e = client.get(f"{API}/equipment/{eq['id']}", headers=admin).json()
    assert e["status"] == "AVAILABLE" and e["last_maintenance_date"] == str(date.today())
    assert client.post(f"{API}/equipment-assignments", headers=admin,
                       json={"equipment_id": eq["id"], "flight_id": f["id"]}).status_code == 201


def test_overdue_maintenance_blocks_allocation(client, admin, factory):
    eq = factory.equipment("PASSENGER_STAIRS", next_maintenance_date=str(date.today() - timedelta(days=1)))
    f = factory.flight()
    r = client.post(f"{API}/equipment-assignments", headers=admin, json={"equipment_id": eq["id"], "flight_id": f["id"]})
    assert r.json()["error"]["code"] == "MAINTENANCE_OVERDUE"
    due = client.get(f"{API}/equipment-maintenance/due", headers=admin).json()
    assert [d["id"] for d in due] == [eq["id"]]


def test_resource_allocation_staff_conflicts_and_history(client, admin, factory):
    s = factory.staff()
    f1, f2 = factory.flight(hours_ahead=4), factory.flight(hours_ahead=4)
    a = factory.post("/resources/allocate", {"resource_type": "STAFF", "resource_id": s["id"], "flight_id": f1["id"],
                                             "role_description": "Ramp lead"})
    r = client.post(f"{API}/resources/allocate", headers=admin,
                    json={"resource_type": "STAFF", "resource_id": s["id"], "flight_id": f2["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "STAFF_CONFLICT"
    g = factory.gate("A1")
    ga = factory.post("/resources/allocate", {"resource_type": "GATE", "resource_id": g["id"], "flight_id": f1["id"]})
    assert ga["assignment_id"]
    dep = datetime.fromisoformat(f1["scheduled_departure"])
    window = {"start_time": (dep - timedelta(minutes=60)).isoformat(), "end_time": dep.isoformat()}
    avail = client.get(f"{API}/resources/availability", headers=admin,
                       params={"resource_type": "STAFF", **window}).json()
    assert s["id"] not in [x["resource_id"] for x in avail]
    assert len(client.get(f"{API}/resources/flight/{f1['id']}", headers=admin).json()) == 2
    client.post(f"{API}/resources/allocations/{a['id']}/release", headers=admin)
    hist = client.get(f"{API}/resources/allocations", headers=admin, params={"resource_type": "STAFF"}).json()
    assert hist["items"][0]["status"] == "RELEASED"
