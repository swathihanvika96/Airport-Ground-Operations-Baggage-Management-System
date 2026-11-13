from tests.conftest import API


def test_dashboard_metrics(client, admin, factory):
    factory.gate("A1")
    g2 = factory.gate("A2")
    c = factory.counter("C1")
    f_sched = factory.flight()
    f_open, pax, _ = factory.checked_in()
    f_cancel = factory.flight()
    client.patch(f"{API}/flights/{f_cancel['id']}/status", headers=admin, json={"status": "CANCELLED"})
    client.post(f"{API}/gates/{g2['id']}/assign", headers=admin, json={"flight_id": f_sched["id"]})
    client.post(f"{API}/counters/{c['id']}/assign", headers=admin, json={"flight_id": f_open["id"]})
    client.post(f"{API}/delays", headers=admin, json={"flight_id": f_sched["id"], "delay_category": "WEATHER",
                                                      "reason": "Fog", "delay_minutes": 30})
    bag = factory.bag(f_open["id"], pax["id"])
    client.patch(f"{API}/baggage/{bag['id']}/status", headers=admin, json={"status": "MISSING"})
    factory.bag(f_open["id"], pax["id"])
    factory.post("/ground-tasks", {"flight_id": f_open["id"], "task_type": "AIRCRAFT_CLEANING"})

    d = client.get(f"{API}/dashboard/overview", headers=admin).json()
    assert d["flights"]["total_flights"] == 3
    assert d["flights"]["delayed_flights"] == 1
    assert d["flights"]["cancelled_flights"] == 1
    assert d["flights"]["check_in_open_flights"] == 1
    assert d["resources"]["available_gates"] == 1 and d["resources"]["total_gates"] == 2
    assert d["resources"]["active_checkin_counters"] == 1
    assert d["baggage"]["baggage_processed"] == 2 and d["baggage"]["missing_baggage"] == 1
    assert d["operations"]["ground_tasks_pending"] == 1
    assert d["operations"]["total_delay_minutes"] == 30
    # any authenticated role can view the dashboard
    agent = factory.user("CHECKIN_AGENT")
    assert client.get(f"{API}/dashboard/flights", headers=agent).status_code == 200


def test_delay_recording_updates_flight(client, admin, factory):
    f = factory.flight()
    d1 = client.post(f"{API}/delays", headers=admin, json={"flight_id": f["id"], "delay_category": "TECHNICAL",
                                                           "reason": "APU", "delay_minutes": 20,
                                                           "responsible_department": "MAINTENANCE"}).json()
    flight = client.get(f"{API}/flights/{f['id']}", headers=admin).json()
    assert flight["status"] == "DELAYED" and d1["expected_departure"] == f["scheduled_departure"]
    client.post(f"{API}/delays", headers=admin, json={"flight_id": f["id"], "delay_category": "GROUND_OPERATIONS",
                                                      "reason": "Late catering", "delay_minutes": 15})
    s = client.get(f"{API}/delays/flight/{f['id']}", headers=admin).json()
    assert s["total_delay_minutes"] == 35 and s["delay_count"] == 2
    assert s["history"][1]["expected_departure"] == d1["updated_departure"]
    rep = client.get(f"{API}/reports/delays/analysis", headers=admin).json()
    assert rep["summary"]["total_delay_minutes"] == 35 and rep["total"] == 2
