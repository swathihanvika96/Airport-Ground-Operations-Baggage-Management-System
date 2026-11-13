from tests.conftest import API


def test_checkin_generates_boarding_pass(client, admin, factory):
    flight, pax, res = factory.checked_in()
    bp = res["boarding_pass"]
    assert res["checkin"]["seat_number"] == "1A"
    assert bp["reference"].startswith(f"BP-{flight['flight_number']}")
    assert client.get(f"{API}/checkin/boarding-pass/{bp['reference']}", headers=admin).json()["id"] == bp["id"]
    booking = client.get(f"{API}/passengers/{pax['id']}/flights", headers=admin).json()[0]
    assert booking["status"] == "CHECKED_IN"


def test_duplicate_checkin_prevented(client, admin, factory):
    flight, pax, _ = factory.checked_in()
    r = client.post(f"{API}/checkin", headers=admin, json={"passenger_id": pax["id"], "flight_id": flight["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_CHECKIN"


def test_checkin_requires_open_flight_and_booking(client, admin, factory):
    f = factory.flight()  # SCHEDULED
    p = factory.passenger(f["id"])
    r = client.post(f"{API}/checkin", headers=admin, json={"passenger_id": p["id"], "flight_id": f["id"]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "CHECKIN_NOT_OPEN"
    open_f = factory.flight(status="CHECK_IN_OPEN")
    r = client.post(f"{API}/checkin", headers=admin, json={"passenger_id": p["id"], "flight_id": open_f["id"]})
    assert r.json()["error"]["code"] == "NOT_BOOKED"


def test_seat_selection_conflict_and_counter_validation(client, admin, factory):
    f = factory.flight(status="CHECK_IN_OPEN")
    p1, p2 = factory.passenger(f["id"]), factory.passenger(f["id"])
    assert client.post(f"{API}/checkin", headers=admin,
                       json={"passenger_id": p1["id"], "flight_id": f["id"], "seat_number": "12C"}).status_code == 201
    r = client.post(f"{API}/checkin", headers=admin,
                    json={"passenger_id": p2["id"], "flight_id": f["id"], "seat_number": "12c"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "SEAT_TAKEN"
    counter = factory.counter("C9")
    r = client.post(f"{API}/checkin", headers=admin,
                    json={"passenger_id": p2["id"], "flight_id": f["id"], "counter_id": counter["id"]})
    assert r.status_code == 400  # counter not assigned to this flight
    client.post(f"{API}/counters/{counter['id']}/assign", headers=admin, json={"flight_id": f["id"]})
    r = client.post(f"{API}/checkin", headers=admin,
                    json={"passenger_id": p2["id"], "flight_id": f["id"], "counter_id": counter["id"]})
    assert r.status_code == 201 and r.json()["checkin"]["counter_id"] == counter["id"]


def test_cancel_and_recheckin_then_board(client, admin, factory):
    flight, pax, res = factory.checked_in()
    cid = res["checkin"]["id"]
    assert client.post(f"{API}/checkin/{cid}/cancel", headers=admin).json()["status"] == "CANCELLED"
    r = client.post(f"{API}/checkin", headers=admin, json={"passenger_id": pax["id"], "flight_id": flight["id"]})
    assert r.status_code == 201 and r.json()["checkin"]["id"] == cid
    assert client.post(f"{API}/checkin/{cid}/board", headers=admin).status_code == 400  # not boarding yet
    client.patch(f"{API}/flights/{flight['id']}/status", headers=admin, json={"status": "BOARDING"})
    assert client.post(f"{API}/checkin/{cid}/board", headers=admin).json()["status"] == "BOARDED"
