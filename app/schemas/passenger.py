from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel
from app.utils.enums import BookingStatus, IdentificationType, PassengerStatus, TravelClass


class PassengerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=30)
    date_of_birth: date | None = None
    nationality: str | None = Field(None, max_length=60)
    id_type: IdentificationType = IdentificationType.PASSPORT
    id_reference: str = Field(min_length=3, max_length=50, description="Synthetic document reference")
    flight_id: int | None = Field(None, description="Optionally book the passenger on a flight immediately")
    travel_class: TravelClass = TravelClass.ECONOMY


class PassengerUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    nationality: str | None = None
    status: PassengerStatus | None = None


class PassengerOut(ORMModel):
    id: int
    first_name: str
    last_name: str
    full_name: str
    email: str | None
    phone: str | None
    date_of_birth: date | None
    nationality: str | None
    id_type: IdentificationType
    id_reference: str
    status: PassengerStatus
    created_at: datetime


class BookingCreate(BaseModel):
    flight_id: int
    travel_class: TravelClass = TravelClass.ECONOMY


class BookingStatusUpdate(BaseModel):
    status: BookingStatus


class BookingOut(ORMModel):
    id: int
    passenger_id: int
    flight_id: int
    booking_reference: str
    travel_class: TravelClass
    status: BookingStatus
    created_at: datetime


class PassengerHistoryItem(BaseModel):
    booking: BookingOut
    flight_number: str
    scheduled_departure: datetime
    flight_status: str
    checkin_id: int | None = None
    seat_number: str | None = None
    boarding_pass_reference: str | None = None
    baggage_count: int = 0


class PassengerHistory(BaseModel):
    passenger: PassengerOut
    history: list[PassengerHistoryItem]
