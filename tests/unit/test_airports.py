import pytest
from pydantic import ValidationError

from app.schemas.airport import AirportCreate
from app.schemas.flight import FlightCreate


def test_airport_code_must_be_three_letters():
    with pytest.raises(ValidationError):
        AirportCreate(code="BL1", name="X Airport", city="X", country="IN")
    assert AirportCreate(code="blr", name="X Airport", city="X", country="IN").code == "blr"


def test_flight_schema_rejects_same_airports_and_bad_times():
    base = dict(flight_number="AI101", airline_name="Air India", airline_code="AI", aircraft_type="A320",
                departure_airport_id=1, arrival_airport_id=2,
                scheduled_departure="2030-01-01T10:00:00", scheduled_arrival="2030-01-01T12:00:00")
    assert FlightCreate(**base).flight_number == "AI101"
    with pytest.raises(ValidationError):
        FlightCreate(**{**base, "arrival_airport_id": 1})
    with pytest.raises(ValidationError):
        FlightCreate(**{**base, "scheduled_arrival": "2030-01-01T09:00:00"})


def test_timezone_aware_datetimes_are_normalised_to_utc():
    f = FlightCreate(flight_number="AI101", airline_name="Air India", airline_code="AI", aircraft_type="A320",
                     departure_airport_id=1, arrival_airport_id=2,
                     scheduled_departure="2030-01-01T10:00:00+05:30", scheduled_arrival="2030-01-01T12:00:00+05:30")
    assert f.scheduled_departure.tzinfo is None and f.scheduled_departure.hour == 4
