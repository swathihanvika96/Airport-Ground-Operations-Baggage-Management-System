"""Test fixtures. Tests run against SQLite by default (fast, no server needed).
Set TEST_DATABASE_URL=mysql+pymysql://user:pw@host/db_test to run the same suite on MySQL."""
import os
import tempfile
from datetime import timedelta

_tmp = os.path.join(tempfile.gettempdir(), f"airport_test_{os.getpid()}.db")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}")
os.environ.setdefault("AUTO_CREATE_TABLES", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("EXPOSE_RESET_TOKEN", "true")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.utils.datetime_utils import utcnow  # noqa: E402

API = settings.API_V1_PREFIX
PASSWORD = "Passw0rd!"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:  # lifespan creates the super admin
        yield c
    Base.metadata.drop_all(bind=engine)


def login(client, username, password):
    r = client.post(f"{API}/auth/token", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return login(client, settings.FIRST_SUPERUSER_EMAIL, settings.FIRST_SUPERUSER_PASSWORD)


class Factory:
    """Builds test data through the public API so business rules are exercised."""

    def __init__(self, client, admin):
        self.c, self.h, self.n = client, admin, 0

    def _uid(self):
        self.n += 1
        return self.n

    def ok(self, resp, code=200):
        assert resp.status_code == code, resp.text
        return resp.json()

    def post(self, path, json=None, code=201, headers=None):
        return self.ok(self.c.post(f"{API}{path}", json=json, headers=headers or self.h), code)

    def patch(self, path, json=None, code=200, headers=None):
        return self.ok(self.c.patch(f"{API}{path}", json=json, headers=headers or self.h), code)

    def get(self, path, code=200, headers=None, params=None):
        return self.ok(self.c.get(f"{API}{path}", headers=headers or self.h, params=params), code)

    def user(self, role):
        n = self._uid()
        email = f"{role.lower()}{n}@airportops.com"
        self.post("/users", {"email": email, "full_name": f"{role} {n}", "password": PASSWORD, "role": role})
        return login(self.c, email, PASSWORD)

    def airport(self, code=None):
        n = self._uid()
        code = code or f"T{chr(65 + n % 26)}{chr(65 + (n // 26) % 26)}"
        return self.post("/airports", {"code": code, "name": f"Test Airport {code}", "city": "City",
                                       "country": "India"})

    def setup_airports(self):
        if not hasattr(self, "_dep"):
            self._dep = self.airport("BLR")
            self._arr = self.airport("BOM")
            self._term = self.post("/terminals", {"airport_id": self._dep["id"], "code": "T1", "name": "Terminal 1",
                                                  "capacity": 3000})
        return self._dep, self._arr, self._term

    def flight(self, hours_ahead=4, status=None, number=None, seat_capacity=180):
        dep, arr, term = self.setup_airports()
        n = self._uid()
        start = utcnow() + timedelta(hours=hours_ahead)
        f = self.post("/flights", {
            "flight_number": number or f"AI{100 + n}", "airline_name": "Air India", "airline_code": "AI",
            "aircraft_type": "A320", "seat_capacity": seat_capacity, "departure_airport_id": dep["id"],
            "arrival_airport_id": arr["id"], "departure_terminal_id": term["id"],
            "scheduled_departure": start.isoformat(), "scheduled_arrival": (start + timedelta(hours=2)).isoformat()})
        path = {"CHECK_IN_OPEN": ["CHECK_IN_OPEN"], "BOARDING": ["CHECK_IN_OPEN", "BOARDING"],
                "DEPARTED": ["CHECK_IN_OPEN", "BOARDING", "DEPARTED"]}.get(status, [])
        for s in path:
            f = self.patch(f"/flights/{f['id']}/status", {"status": s})
        return f

    def gate(self, number=None):
        _, _, term = self.setup_airports()
        return self.post("/gates", {"terminal_id": term["id"], "gate_number": number or f"G{self._uid()}"})

    def counter(self, number=None):
        _, _, term = self.setup_airports()
        return self.post("/counters", {"terminal_id": term["id"], "counter_number": number or f"C{self._uid()}"})

    def passenger(self, flight_id=None):
        n = self._uid()
        body = {"first_name": "Test", "last_name": f"Pax{n}", "email": f"pax{n}@example.com",
                "id_type": "PASSPORT", "id_reference": f"SYN{n:06d}"}
        if flight_id:
            body["flight_id"] = flight_id
        return self.post("/passengers", body)

    def checked_in(self, flight=None):
        flight = flight or self.flight(status="CHECK_IN_OPEN")
        pax = self.passenger(flight["id"])
        res = self.post("/checkin", {"passenger_id": pax["id"], "flight_id": flight["id"]})
        return flight, pax, res

    def bag(self, flight_id, passenger_id, **extra):
        return self.post("/baggage", {"passenger_id": passenger_id, "flight_id": flight_id, "weight_kg": 20,
                                      "category": "CHECKED", **extra})

    def screened_bag(self):
        flight, pax, _ = self.checked_in()
        bag = self.bag(flight["id"], pax["id"])
        self.patch(f"/baggage/{bag['id']}/status", {"status": "CHECKIN_COMPLETED"})
        self.post(f"/baggage/{bag['id']}/screenings", {"result": "CLEARED"})
        return flight, pax, bag

    def staff(self, **extra):
        n = self._uid()
        return self.post("/ground-staff", {"employee_code": f"EMP{n:03d}", "full_name": f"Staff {n}",
                                           "department": "RAMP_OPERATIONS", "designation": "Ramp Agent",
                                           "skills": ["loading"], **extra})

    def equipment(self, etype="BAGGAGE_CART", **extra):
        n = self._uid()
        return self.post("/equipment", {"equipment_code": f"EQ{n:03d}", "name": f"Equipment {n}",
                                        "equipment_type": etype, **extra})


@pytest.fixture()
def factory(client, admin):
    return Factory(client, admin)
