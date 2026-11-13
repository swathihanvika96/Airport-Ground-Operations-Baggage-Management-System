from tests.conftest import API

REPORTS = ["/reports/flights/daily", "/reports/flights/monthly-performance", "/reports/baggage/handling",
           "/reports/baggage/missing", "/reports/staff/performance", "/reports/equipment/utilization",
           "/reports/delays/analysis", "/reports/turnarounds"]


def test_all_reports_json_and_csv(client, admin, factory):
    flight, pax, bag = factory.screened_bag()
    factory.equipment()
    factory.staff()
    for path in REPORTS:
        r = client.get(f"{API}{path}", headers=admin)
        assert r.status_code == 200, (path, r.text)
        assert {"report", "items", "total", "page", "summary"} <= set(r.json())
        c = client.get(f"{API}{path}", headers=admin, params={"format": "csv"})
        assert c.status_code == 200 and c.headers["content-type"].startswith("text/csv"), path


def test_daily_report_pagination_sorting_and_csv(client, admin, factory):
    for _ in range(3):
        factory.flight()
    r = client.get(f"{API}/reports/flights/daily", headers=admin, params={"size": 2, "page": 1}).json()
    assert r["total"] == 3 and len(r["items"]) == 2 and r["pages"] == 2
    asc = client.get(f"{API}/reports/flights/daily", headers=admin,
                     params={"sort_by": "flight_number", "sort_order": "asc"}).json()["items"]
    assert [i["flight_number"] for i in asc] == sorted(i["flight_number"] for i in asc)
    bad = client.get(f"{API}/reports/flights/daily", headers=admin, params={"sort_by": "nope"})
    assert bad.status_code == 400
    csv_text = client.get(f"{API}/reports/flights/daily", headers=admin, params={"format": "csv"}).text
    assert csv_text.splitlines()[0].startswith("flight_id,flight_number") and len(csv_text.splitlines()) == 4


def test_reports_require_permission(client, factory):
    agent = factory.user("CHECKIN_AGENT")
    assert client.get(f"{API}/reports/flights/daily", headers=agent).status_code == 403


def test_date_range_validation(client, admin):
    r = client.get(f"{API}/reports/delays/analysis", headers=admin,
                   params={"date_from": "2030-02-01", "date_to": "2030-01-01"})
    assert r.status_code == 400
