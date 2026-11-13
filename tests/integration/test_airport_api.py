from tests.conftest import API


def test_airport_crud_and_search(client, admin, factory):
    a = factory.airport("DEL")
    assert a["code"] == "DEL"
    assert client.post(f"{API}/airports", headers=admin, json={"code": "del", "name": "Dup", "city": "c",
                                                               "country": "IN"}).status_code == 409
    factory.airport("MAA")
    r = client.get(f"{API}/airports", headers=admin, params={"q": "DEL"}).json()
    assert r["total"] == 1
    assert client.get(f"{API}/airports/code/del", headers=admin).json()["id"] == a["id"]
    r = client.patch(f"{API}/airports/{a['id']}/status", headers=admin, json={"operational_status": "LIMITED"})
    assert r.json()["operational_status"] == "LIMITED"
    r = client.get(f"{API}/airports", headers=admin, params={"status": "LIMITED"}).json()
    assert [x["code"] for x in r["items"]] == ["DEL"]


def test_terminal_and_mapping(client, admin, factory):
    dep, _, term = factory.setup_airports()
    assert client.post(f"{API}/terminals", headers=admin, json={"airport_id": dep["id"], "code": "t1",
                                                                "name": "dup"}).status_code == 409
    factory.gate("A1")
    factory.counter("C1")
    m = client.get(f"{API}/terminals/{term['id']}/map", headers=admin).json()
    assert m["summary"] == {"total_gates": 1, "available_gates": 1, "total_counters": 1}
    r = client.patch(f"{API}/terminals/{term['id']}", headers=admin, json={"capacity": 5000})
    assert r.json()["capacity"] == 5000
