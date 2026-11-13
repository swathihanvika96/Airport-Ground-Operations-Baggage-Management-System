from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel
from app.utils.enums import ScreeningStatus


class ScreeningCreate(BaseModel):
    result: Literal["CLEARED", "HOLD", "REJECTED"]
    machine_id: str | None = Field(None, max_length=30)
    remarks: str | None = Field(None, max_length=500, description="Inspection remarks")
    hold_reason: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def _check(self):
        if self.result in ("HOLD", "REJECTED") and not self.hold_reason:
            raise ValueError("hold_reason is required when result is HOLD or REJECTED")
        return self


class ScreeningRelease(BaseModel):
    remarks: str | None = Field(None, max_length=500)


class ScreeningOut(ORMModel):
    id: int
    baggage_id: int
    status: ScreeningStatus
    screening_officer_id: int | None
    screened_at: datetime
    machine_id: str | None
    remarks: str | None
    hold_reason: str | None
    released_at: datetime | None
    released_by_id: int | None
    release_remarks: str | None
