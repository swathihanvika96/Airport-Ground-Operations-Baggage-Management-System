from tests.conftest import API


def test_register_with_generated_and_custom_tag(client, admin, factory):
    flight, pax, _ = factory.checked_in()
    bag = factory.bag(flight["id"], pax["id"])
    assert bag["status"] == "REGISTERED" and bag["tag_number"].startswith("AI") and bag["destination"] == "BOM"
    custom = factory.bag(flight["id"], pax["id"], tag_number="ai12345678")
    assert custom["tag_number"] == "AI12345678"
    r = client.post(f"{API}/baggage", headers=admin, json={"passenger_id": pax["id"], "flight_id": flight["id"],
                                                           "weight_kg": 10, "tag_number": "AI12345678"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_BAGGAGE_TAG"


def test_weight_limit_and_booking_required(client, admin, factory):
    flight, pax, _ = factory.checked_in()
    r = client.post(f"{API}/baggage", headers=admin, json={"passenger_id": pax["id"], "flight_id": flight["id"],
                                                           "weight_kg": 40, "category": "CHECKED"})
    assert r.json()["error"]["code"] == "BAGGAGE_OVERWEIGHT"
    other = factory.passenger()
    r = client.post(f"{API}/baggage", headers=admin, json={"passenger_id": other["id"], "flight_id": flight["id"],
                                                           "weight_kg": 10})
    assert r.json()["error"]["code"] == "NOT_BOOKED"


def test_full_tracking_lifecycle_with_history(client, admin, factory):
    flight, pax, bag = factory.screened_bag()
    for status in ("SORTING", "LOADED", "IN_TRANSIT", "UNLOADED", "DELIVERED"):
        r = client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin, json={"status": status,
                                                                                   "location": f"loc-{status}"})
        assert r.status_code == 200, r.text
    hist = client.get(f"{API}/baggage/{bag['id']}/history", headers=admin).json()
    assert [h["status"] for h in hist] == ["REGISTERED", "CHECKIN_COMPLETED", "SECURITY_SCREENING", "SORTING",
                                           "LOADED", "IN_TRANSIT", "UNLOADED", "DELIVERED"]
    assert all(h["timestamp"] for h in hist)
    view = client.get(f"{API}/baggage/track/{bag['tag_number']}", headers=admin).json()
    assert view["baggage"]["status"] == "DELIVERED" and len(view["timeline"]) == 8
    r = client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin, json={"status": "SORTING"})
    assert r.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


def test_sorting_requires_screening(client, admin, factory):
    flight, pax, _ = factory.checked_in()
    bag = factory.bag(flight["id"], pax["id"])
    client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin, json={"status": "CHECKIN_COMPLETED"})
    client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin, json={"status": "SECURITY_SCREENING"})
    r = client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin, json={"status": "SORTING"})
    assert r.json()["error"]["code"] == "SCREENING_REQUIRED"


def test_screening_hold_and_release(client, admin, factory):
    handler = factory.user("BAGGAGE_HANDLING_STAFF")
    flight, pax, _ = factory.checked_in()
    bag = factory.bag(flight["id"], pax["id"])
    client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin, json={"status": "CHECKIN_COMPLETED"})
    s = client.post(f"{API}/baggage/{bag['id']}/screenings", headers=handler,
                    json={"result": "HOLD", "hold_reason": "Dense object", "remarks": "Manual inspection"}).json()
    assert s["status"] == "HOLD" and s["screening_officer_id"]
    b = client.get(f"{API}/baggage/{bag['id']}", headers=admin).json()
    assert b["is_on_hold"] and b["status"] == "SECURITY_SCREENING"
    r = client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin, json={"status": "SORTING"})
    assert r.json()["error"]["code"] == "BAGGAGE_ON_HOLD"
    assert client.post(f"{API}/baggage/{bag['id']}/screenings", headers=handler,
                       json={"result": "HOLD"}).status_code == 422  # hold_reason required
    rel = client.post(f"{API}/baggage/screenings/{s['id']}/release", headers=handler, json={"remarks": "OK"}).json()
    assert rel["status"] == "RELEASED"
    assert client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin,
                        json={"status": "SORTING"}).status_code == 200


def test_missing_baggage_notifies_and_reports(client, admin, factory):
    handler = factory.user("BAGGAGE_HANDLING_STAFF")
    flight, pax, bag = factory.screened_bag()
    client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin,
                 json={"status": "MISSING", "remarks": "Not found at belt"})
    notes = client.get(f"{API}/notifications", headers=handler,
                       params={"notification_type": "MISSING_BAGGAGE"}).json()
    assert notes["total"] == 1
    rep = client.get(f"{API}/reports/baggage/missing", headers=admin).json()
    assert rep["total"] == 1 and rep["items"][0]["tag_number"] == bag["tag_number"]
