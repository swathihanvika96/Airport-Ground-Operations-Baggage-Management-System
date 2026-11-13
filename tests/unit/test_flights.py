import pytest

from app.core.exceptions import InvalidTransitionError
from app.services.flight_service import validate_flight_transition
from app.utils.enums import FlightStatus as FS


@pytest.mark.parametrize("cur,target", [
    (FS.SCHEDULED, FS.CHECK_IN_OPEN), (FS.CHECK_IN_OPEN, FS.BOARDING), (FS.BOARDING, FS.DEPARTED),
    (FS.DEPARTED, FS.ARRIVED), (FS.SCHEDULED, FS.DELAYED), (FS.DELAYED, FS.BOARDING), (FS.SCHEDULED, FS.CANCELLED),
])
def test_valid_flight_transitions(cur, target):
    validate_flight_transition(cur, target)


@pytest.mark.parametrize("cur,target", [
    (FS.SCHEDULED, FS.DEPARTED), (FS.SCHEDULED, FS.ARRIVED), (FS.ARRIVED, FS.SCHEDULED),
    (FS.CANCELLED, FS.SCHEDULED), (FS.DEPARTED, FS.BOARDING), (FS.CHECK_IN_OPEN, FS.ARRIVED),
])
def test_invalid_flight_transitions(cur, target):
    with pytest.raises(InvalidTransitionError):
        validate_flight_transition(cur, target)
