from tests.conftest import API


def test_register_search_and_history(client, admin, factory):
    f = factory.flight()
    p = factory.passenger(f["id"])
    assert client.post(f"{API}/passengers", headers=admin, json={
        "first_name": "Dup", "last_name": "X", "id_type": "PASSPORT", "id_reference": p["id_reference"]}).status_code == 409
    assert client.get(f"{API}/passengers", headers=admin, params={"q": p["last_name"]}).json()["total"] == 1
    assert client.get(f"{API}/passengers", headers=admin, params={"flight_id": f["id"]}).json()["total"] == 1
    booking = client.get(f"{API}/passengers/{p['id']}/flights", headers=admin).json()[0]
    assert client.get(f"{API}/passengers", headers=admin,
                      params={"q": booking["booking_reference"]}).json()["total"] == 1
    hist = client.get(f"{API}/passengers/{p['id']}/history", headers=admin).json()
    assert hist["history"][0]["flight_number"] == f["flight_number"]


def test_duplicate_flight_mapping_rejected(client, admin, factory):
    f = factory.flight()
    p = factory.passenger(f["id"])
    assert client.post(f"{API}/passengers/{p['id']}/flights", headers=admin,
                       json={"flight_id": f["id"]}).status_code == 409


def test_flight_capacity_enforced(client, admin, factory):
    f = factory.flight(seat_capacity=1)
    factory.passenger(f["id"])
    p2 = factory.passenger()
    r = client.post(f"{API}/passengers/{p2['id']}/flights", headers=admin, json={"flight_id": f["id"]})
    assert r.status_code == 400
