from fastapi import APIRouter

from app.api.dependencies import DB, CurrentUser, allow
from app.core.constants import BAGGAGE_STATUS_TRANSITIONS
from app.core.permissions import Permissions
from app.models.user import User
from app.schemas.baggage import BaggageOut
from app.schemas.baggage_tracking import BaggageStatusUpdate, BaggageTrackingView, TrackingEventOut
from app.services.baggage_tracking_service import BaggageTrackingService

router = APIRouter(prefix="/baggage", tags=["Baggage Tracking"])


@router.get("/status-transitions", summary="Valid baggage lifecycle transitions")
def transitions(_: CurrentUser):
    return {k.value: sorted(v.value for v in vs) for k, vs in BAGGAGE_STATUS_TRANSITIONS.items()}


@router.patch("/{baggage_id}/status", response_model=BaggageOut,
              summary="Update baggage lifecycle status (timestamped history row is recorded)")
def update_status(baggage_id: int, data: BaggageStatusUpdate, db: DB, user: User = allow(Permissions.BAGGAGE_TRACK)):
    return BaggageTrackingService(db).update_status(baggage_id, data.status, user, data.location, data.remarks)


@router.get("/{baggage_id}/history", response_model=list[TrackingEventOut])
def history(baggage_id: int, db: DB, _: CurrentUser):
    return BaggageTrackingService(db).history(baggage_id)


@router.get("/track/{tag_number}", response_model=BaggageTrackingView, summary="Track baggage by tag number")
def track(tag_number: str, db: DB, _: CurrentUser):
    return BaggageTrackingService(db).track_by_tag(tag_number)
