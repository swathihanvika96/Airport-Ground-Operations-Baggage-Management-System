from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.baggage import BaggageOut
from app.schemas.common import ORMModel
from app.utils.enums import BaggageStatus


class BaggageStatusUpdate(BaseModel):
    status: BaggageStatus
    location: str | None = Field(None, max_length=100)
    remarks: str | None = Field(None, max_length=500)


class TrackingEventOut(ORMModel):
    id: int
    baggage_id: int
    previous_status: BaggageStatus | None
    status: BaggageStatus
    location: str | None
    remarks: str | None
    updated_by_id: int | None
    timestamp: datetime


class BaggageTrackingView(BaseModel):
    baggage: BaggageOut
    timeline: list[TrackingEventOut]
