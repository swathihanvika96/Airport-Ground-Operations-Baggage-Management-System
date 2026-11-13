from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.utils.enums import AirportStatus


class AirportBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str | None = None
    country: str = Field(min_length=2, max_length=100)
    timezone: str = "UTC"
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    operational_status: AirportStatus = AirportStatus.OPERATIONAL


class AirportCreate(AirportBase):
    code: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$", description="IATA code")
    icao_code: str | None = Field(None, min_length=4, max_length=4, pattern=r"^[A-Za-z]{4}$")


class AirportUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    timezone: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    operational_status: AirportStatus | None = None


class AirportStatusUpdate(BaseModel):
    operational_status: AirportStatus


class AirportOut(ORMModel):
    id: int
    code: str
    icao_code: str | None
    name: str
    city: str
    state: str | None
    country: str
    timezone: str
    latitude: float | None
    longitude: float | None
    operational_status: AirportStatus
    created_at: datetime
