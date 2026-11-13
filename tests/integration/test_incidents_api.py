from tests.conftest import API


def test_incident_lifecycle_and_history(client, admin, factory):
    manager = factory.user("AIRPORT_OPERATIONS_MANAGER")
    gate_agent = factory.user("GATE_AGENT")
    f = factory.flight()
    _, _, term = factory.setup_airports()
    inc = client.post(f"{API}/incidents", headers=gate_agent, json={
        "title": "Jet bridge fault", "description": "Bridge stuck", "category": "EQUIPMENT_FAILURE",
        "severity": "HIGH", "flight_id": f["id"], "terminal_id": term["id"]}).json()
    assert inc["status"] == "OPEN" and inc["reference"].startswith("INC-")
    assert client.get(f"{API}/notifications", headers=manager,
                      params={"notification_type": "OPERATIONAL_INCIDENT"}).json()["total"] == 1
    # gate agents can report but not manage
    assert client.patch(f"{API}/incidents/{inc['id']}/status", headers=gate_agent,
                        json={"status": "IN_PROGRESS"}).status_code == 403
    client.post(f"{API}/incidents/{inc['id']}/assign", headers=manager, json={"assigned_team": "Engineering"})
    client.patch(f"{API}/incidents/{inc['id']}/status", headers=manager, json={"status": "IN_PROGRESS"})
    r = client.patch(f"{API}/incidents/{inc['id']}/status", headers=manager, json={"status": "RESOLVED"})
    assert r.status_code == 400  # resolution details required
    r = client.patch(f"{API}/incidents/{inc['id']}/status", headers=manager,
                     json={"status": "RESOLVED", "resolution_details": "Hydraulics reset"})
    assert r.json()["resolved_at"]
    client.patch(f"{API}/incidents/{inc['id']}/status", headers=manager, json={"status": "CLOSED"})
    detail = client.get(f"{API}/incidents/{inc['id']}", headers=admin).json()
    assert [h["action"] for h in detail["history"]] == ["CREATED", "ASSIGNED", "STATUS_CHANGED", "STATUS_CHANGED",
                                                        "STATUS_CHANGED"]
    assert client.patch(f"{API}/incidents/{inc['id']}/status", headers=manager,
                        json={"status": "OPEN"}).status_code == 400
    assert client.get(f"{API}/audit-logs", headers=admin,
                      params={"action": "INCIDENT_RESOLVED"}).json()["total"] == 1
    assert client.get(f"{API}/incidents", headers=admin, params={"severity": "HIGH"}).json()["total"] == 1
