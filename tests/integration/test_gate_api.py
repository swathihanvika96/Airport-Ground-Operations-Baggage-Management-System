from tests.conftest import API


def test_gate_assignment_and_conflict_prevention(client, admin, factory):
    gate = factory.gate("A1")
    f1, f2 = factory.flight(hours_ahead=4), factory.flight(hours_ahead=4)
    r = client.post(f"{API}/gates/{gate['id']}/assign", headers=admin, json={"flight_id": f1["id"]})
    assert r.status_code == 201, r.text
    assert client.get(f"{API}/gates/{gate['id']}", headers=admin).json()["status"] == "OCCUPIED"
    assert client.get(f"{API}/flights/{f1['id']}", headers=admin).json()["gate_number"] == "A1"
    # overlapping window for another flight -> conflict
    r = client.post(f"{API}/gates/{gate['id']}/assign", headers=admin, json={"flight_id": f2["id"]})
    assert r.status_code == 409 and r.json()["error"]["details"][0]["flight_id"] == f1["id"]
    # non-overlapping flight is fine
    f3 = factory.flight(hours_ahead=12)
    assert client.post(f"{API}/gates/{gate['id']}/assign", headers=admin, json={"flight_id": f3["id"]}).status_code == 201


def test_gate_change_releases_previous_and_notifies(client, admin, factory):
    g1, g2 = factory.gate("A1"), factory.gate("A2")
    gate_agent = factory.user("GATE_AGENT")
    f = factory.flight()
    client.post(f"{API}/gates/{g1['id']}/assign", headers=admin, json={"flight_id": f["id"]})
    r = client.post(f"{API}/gates/{g2['id']}/assign", headers=gate_agent, json={"flight_id": f["id"]})
    assert r.status_code == 201
    hist = client.get(f"{API}/gates/assignments", headers=admin, params={"flight_id": f["id"]}).json()["items"]
    assert sorted(a["status"] for a in hist) == ["ACTIVE", "CANCELLED"]
    assert client.get(f"{API}/gates/{g1['id']}", headers=admin).json()["status"] == "AVAILABLE"
    notes = client.get(f"{API}/notifications", headers=gate_agent, params={"notification_type": "GATE_CHANGE"}).json()
    assert notes["total"] == 1


def test_gate_availability_and_maintenance(client, admin, factory):
    g1, g2 = factory.gate("A1"), factory.gate("A2")
    f = factory.flight()
    client.post(f"{API}/gates/{g1['id']}/assign", headers=admin, json={"flight_id": f["id"]})
    win = {"start_time": f["scheduled_departure"], "end_time": f["scheduled_arrival"]}
    avail = client.get(f"{API}/gates/available", headers=admin, params=win).json()
    assert [g["id"] for g in avail] == [g2["id"]]
    # cannot put an occupied gate into maintenance
    assert client.patch(f"{API}/gates/{g1['id']}", headers=admin, json={"status": "MAINTENANCE"}).status_code == 409
    client.patch(f"{API}/gates/{g2['id']}", headers=admin, json={"status": "MAINTENANCE"})
    assert client.post(f"{API}/gates/{g2['id']}/assign", headers=admin,
                       json={"flight_id": factory.flight(hours_ahead=20)["id"]}).status_code == 400


def test_counter_assignment_conflict_and_release(client, admin, factory):
    c = factory.counter("C1")
    f1, f2 = factory.flight(), factory.flight()
    a = client.post(f"{API}/counters/{c['id']}/assign", headers=admin, json={"flight_id": f1["id"]}).json()
    assert client.get(f"{API}/counters/{c['id']}", headers=admin).json()["status"] == "OPEN"
    assert client.post(f"{API}/counters/{c['id']}/assign", headers=admin,
                       json={"flight_id": f2["id"]}).status_code == 409
    client.post(f"{API}/counters/assignments/{a['id']}/release", headers=admin)
    assert client.get(f"{API}/counters/{c['id']}", headers=admin).json()["status"] == "AVAILABLE"
    assert client.post(f"{API}/counters/{c['id']}/assign", headers=admin,
                       json={"flight_id": f2["id"]}).status_code == 201


def test_departure_releases_gate(client, admin, factory):
    g = factory.gate("A1")
    f = factory.flight()
    client.post(f"{API}/gates/{g['id']}/assign", headers=admin, json={"flight_id": f["id"]})
    for s in ("CHECK_IN_OPEN", "BOARDING", "DEPARTED"):
        client.patch(f"{API}/flights/{f['id']}/status", headers=admin, json={"status": s})
    assert client.get(f"{API}/gates/{g['id']}", headers=admin).json()["status"] == "AVAILABLE"
