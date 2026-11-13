from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.boarding_pass import BoardingPassOut
from app.schemas.common import ORMModel
from app.utils.enums import CheckInChannel, CheckInStatus


class CheckInCreate(BaseModel):
    passenger_id: int
    flight_id: int
    seat_number: str | None = Field(None, pattern=r"^[1-9][0-9]?[A-Ka-k]$", description="e.g. 12C; auto-assigned if omitted")
    counter_id: int | None = None
    channel: CheckInChannel = CheckInChannel.COUNTER


class SeatChangeRequest(BaseModel):
    seat_number: str = Field(pattern=r"^[1-9][0-9]?[A-Ka-k]$")


class CheckInOut(ORMModel):
    id: int
    passenger_id: int
    flight_id: int
    booking_id: int
    counter_id: int | None
    seat_number: str
    checkin_time: datetime
    boarded_at: datetime | None
    channel: CheckInChannel
    status: CheckInStatus
    baggage_count: int
    checked_in_by_id: int | None


class CheckInResult(BaseModel):
    checkin: CheckInOut
    boarding_pass: BoardingPassOut
