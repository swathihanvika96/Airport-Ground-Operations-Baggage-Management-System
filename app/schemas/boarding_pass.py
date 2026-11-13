from datetime import datetime

from app.schemas.common import ORMModel


class BoardingPassOut(ORMModel):
    id: int
    checkin_id: int
    reference: str
    flight_id: int
    passenger_id: int
    seat_number: str
    gate_number: str | None
    boarding_time: datetime | None
    boarding_group: str
    sequence_number: int
    is_valid: bool
    issued_at: datetime
