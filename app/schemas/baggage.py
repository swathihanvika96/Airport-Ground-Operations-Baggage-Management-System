from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.utils.enums import BaggageCategory, BaggageStatus


class BaggageCreate(BaseModel):
    passenger_id: int
    flight_id: int
    weight_kg: float = Field(gt=0, le=100)
    category: BaggageCategory = BaggageCategory.CHECKED
    destination: str | None = Field(None, min_length=3, max_length=3, description="IATA code; defaults to flight arrival")
    tag_number: str | None = Field(None, min_length=6, max_length=20, pattern=r"^[A-Za-z0-9]+$",
                                   description="Auto-generated if omitted")
    description: str | None = Field(None, max_length=255)


class BaggageUpdate(BaseModel):
    weight_kg: float | None = Field(None, gt=0, le=100)
    category: BaggageCategory | None = None
    destination: str | None = Field(None, min_length=3, max_length=3)
    description: str | None = None


class BaggageOut(ORMModel):
    id: int
    tag_number: str
    passenger_id: int
    flight_id: int
    checkin_id: int | None
    weight_kg: float
    category: BaggageCategory
    destination: str
    description: str | None
    status: BaggageStatus
    current_location: str | None
    is_on_hold: bool
    created_at: datetime
    updated_at: datetime
