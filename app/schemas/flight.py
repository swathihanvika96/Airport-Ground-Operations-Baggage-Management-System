from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel, UTCDateTime
from app.utils.enums import FlightStatus


class FlightCreate(BaseModel):
    flight_number: str = Field(min_length=3, max_length=10, pattern=r"^[A-Za-z0-9]{2,3}\d{1,5}[A-Za-z]?$")
    airline_name: str = Field(min_length=2, max_length=100)
    airline_code: str = Field(min_length=2, max_length=3)
    aircraft_type: str = Field(min_length=2, max_length=50)
    aircraft_registration: str | None = Field(None, max_length=20)
    seat_capacity: int = Field(180, ge=1, le=900)
    departure_airport_id: int
    arrival_airport_id: int
    departure_terminal_id: int | None = None
    scheduled_departure: UTCDateTime
    scheduled_arrival: UTCDateTime

    @model_validator(mode="after")
    def _check(self):
        if self.departure_airport_id == self.arrival_airport_id:
            raise ValueError("Departure and arrival airports must differ")
        if self.scheduled_arrival <= self.scheduled_departure:
            raise ValueError("scheduled_arrival must be after scheduled_departure")
        self.flight_number = self.flight_number.upper()
        self.airline_code = self.airline_code.upper()
        return self


class FlightUpdate(BaseModel):
    airline_name: str | None = None
    aircraft_type: str | None = None
    aircraft_registration: str | None = None
    seat_capacity: int | None = Field(None, ge=1, le=900)
    departure_terminal_id: int | None = None
    scheduled_departure: UTCDateTime | None = None
    scheduled_arrival: UTCDateTime | None = None


class FlightStatusUpdate(BaseModel):
    status: FlightStatus
    actual_time: UTCDateTime | None = Field(None, description="Actual departure/arrival time (defaults to now)")
    remarks: str | None = None


class FlightOut(ORMModel):
    id: int
    flight_number: str
    airline_name: str
    airline_code: str
    aircraft_type: str
    aircraft_registration: str | None
    seat_capacity: int
    departure_airport_id: int
    arrival_airport_id: int
    departure_airport_code: str | None = None
    arrival_airport_code: str | None = None
    departure_terminal_id: int | None
    gate_id: int | None
    gate_number: str | None = None
    scheduled_departure: datetime
    scheduled_arrival: datetime
    estimated_departure: datetime | None
    actual_departure: datetime | None
    actual_arrival: datetime | None
    status: FlightStatus
    created_at: datetime
